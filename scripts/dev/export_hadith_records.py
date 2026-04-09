from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect


REQUIRED_OUTPUT_FIELDS: Tuple[str, ...] = (
    "canonical_ref",
    "collection_source_id",
    "collection_slug",
    "collection_hadith_number",
    "book_number",
    "chapter_number",
    "numbering_quality",
    "english_text",
)

OPTIONAL_OUTPUT_FIELDS: Tuple[str, ...] = (
    "arabic_text",
    "english_narrator",
    "book_title_en",
    "chapter_title_en",
    "in_book_hadith_number",
    "grading_label",
    "grading_text",
)

COLUMN_ALIASES: Dict[str, Sequence[str]] = {
    "canonical_ref": (
        "canonical_ref",
        "canonical_ref_collection",
    ),
    "collection_source_id": (
        "collection_source_id",
        "source_id",
    ),
    "collection_slug": (
        "collection_slug",
    ),
    "collection_hadith_number": (
        "collection_hadith_number",
        "hadith_number",
    ),
    "book_number": (
        "book_number",
    ),
    "chapter_number": (
        "chapter_number",
    ),
    "numbering_quality": (
        "numbering_quality",
    ),
    "english_text": (
        "english_text",
    ),
    "arabic_text": (
        "arabic_text",
    ),
    "english_narrator": (
        "english_narrator",
        "narrator_en",
    ),
    "book_title_en": (
        "book_title_en",
        "book_title",
    ),
    "chapter_title_en": (
        "chapter_title_en",
        "chapter_title",
    ),
    "in_book_hadith_number": (
        "in_book_hadith_number",
    ),
    "grading_label": (
        "grading_label",
    ),
    "grading_text": (
        "grading_text",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export canonical hadith records from PostgreSQL into JSON for topical indexing."
    )
    parser.add_argument(
        "--output",
        default=r".\tmp\hadith_records.json",
        help="Path to write exported records JSON.",
    )
    parser.add_argument(
        "--collection-source-id",
        default="hadith:sahih-al-bukhari-en",
        help="Collection source id to export. Default is Bukhari English.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of rows to export for smoke testing.",
    )
    parser.add_argument(
        "--table",
        default=None,
        help="Optional explicit table name if you already know it.",
    )
    return parser.parse_args()


def get_engine() -> Engine:
    database_url = os.getenv("DATABASE_URL") or os.getenv("DALIL_DATABASE_URL")
    if not database_url:
        raise SystemExit(
            "Neither DATABASE_URL nor DALIL_DATABASE_URL is set in this shell session. "
            "Set one of them first, then rerun this export."
        )
    return create_engine(database_url)


def resolve_column_name(column_names: Iterable[str], logical_name: str) -> Optional[str]:
    available = {name.lower(): name for name in column_names}
    for alias in COLUMN_ALIASES.get(logical_name, (logical_name,)):
        actual = available.get(alias.lower())
        if actual:
            return actual
    return None


def table_score(column_names: Iterable[str]) -> int:
    score = 0
    for field in REQUIRED_OUTPUT_FIELDS:
        if resolve_column_name(column_names, field):
            score += 3
    for field in OPTIONAL_OUTPUT_FIELDS:
        if resolve_column_name(column_names, field):
            score += 1
    return score


def choose_table(engine: Engine, explicit_table: Optional[str]) -> str:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if explicit_table:
        if explicit_table not in table_names:
            raise SystemExit(
                f"Table '{explicit_table}' was not found. Available tables: {table_names}"
            )
        return explicit_table

    preferred_names = [
        "hadith_entries",
        "hadith_entry",
        "canonical_hadith_entries",
        "canonical_hadith_entry",
        "hadith_records",
        "hadith",
    ]

    for name in preferred_names:
        if name in table_names:
            cols = [col["name"] for col in inspector.get_columns(name)]
            if table_score(cols) >= 20:
                return name

    best_name: Optional[str] = None
    best_score = -1
    for name in table_names:
        cols = [col["name"] for col in inspector.get_columns(name)]
        score = table_score(cols)
        if score > best_score:
            best_score = score
            best_name = name

    if not best_name or best_score < 18:
        raise SystemExit(
            "Could not confidently identify the canonical hadith table. "
            "Re-run with --table <exact_table_name> once you know it."
        )

    return best_name


def build_field_mapping(column_names: Iterable[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    missing_required: List[str] = []

    for field in REQUIRED_OUTPUT_FIELDS:
        actual = resolve_column_name(column_names, field)
        if not actual:
            missing_required.append(field)
        else:
            mapping[field] = actual

    if missing_required:
        raise SystemExit(
            "Chosen table is missing required columns for export: "
            + ", ".join(missing_required)
        )

    for field in OPTIONAL_OUTPUT_FIELDS:
        actual = resolve_column_name(column_names, field)
        if actual:
            mapping[field] = actual

    return mapping


def export_records(
    engine: Engine,
    table_name: str,
    field_mapping: Dict[str, str],
    collection_source_id: str,
    limit: Optional[int],
) -> List[Dict[str, object]]:
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)

    select_columns = [
        table.c[actual_name].label(logical_name)
        for logical_name, actual_name in field_mapping.items()
    ]

    source_col_name = field_mapping.get("collection_source_id")
    stmt = select(*select_columns)

    if source_col_name:
        stmt = stmt.where(table.c[source_col_name] == collection_source_id)

    canonical_ref_col = field_mapping.get("canonical_ref")
    if canonical_ref_col:
        stmt = stmt.order_by(table.c[canonical_ref_col])

    if limit is not None:
        stmt = stmt.limit(limit)

    try:
        with engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
    except SQLAlchemyError as exc:
        raise SystemExit(f"Database query failed: {exc}") from exc

    exported: List[Dict[str, object]] = []
    for row in rows:
        record = dict(row)
        for key, value in list(record.items()):
            if isinstance(value, Path):
                record[key] = str(value)
        exported.append(record)

    return exported


def main() -> int:
    args = parse_args()
    engine = get_engine()

    table_name = choose_table(engine, args.table)
    inspector = inspect(engine)
    column_names = [col["name"] for col in inspector.get_columns(table_name)]
    field_mapping = build_field_mapping(column_names)

    records = export_records(
        engine=engine,
        table_name=table_name,
        field_mapping=field_mapping,
        collection_source_id=args.collection_source_id,
        limit=args.limit,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Exported {len(records)} records from table '{table_name}' -> {output_path}")
    print(f"Collection source id filter: {args.collection_source_id}")
    print(f"Detected field mapping: {json.dumps(field_mapping, indent=2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())