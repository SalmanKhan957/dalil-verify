from __future__ import annotations

import argparse
import csv
from pathlib import Path

from domains.quran.repositories import (
    DEFAULT_QURAN_ARABIC_PATH,
    DEFAULT_QURAN_TEXT_WORK_SOURCE_ID,
    DEFAULT_QURAN_TRANSLATION_PATH,
    DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID,
    SqlAlchemyQuranRepository,
    build_arabic_work_seed,
    build_surah_rows_from_arabic_csv,
    build_translation_work_seed,
)
from infrastructure.db.base import Base
from infrastructure.db.session import get_session, make_engine

EXPECTED_AYAH_COUNT = 6236



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load canonical Quran Arabic rows and one translation work into the DALIL Postgres canonical store."
    )
    parser.add_argument("--arabic-csv", type=Path, default=DEFAULT_QURAN_ARABIC_PATH)
    parser.add_argument("--translation-csv", type=Path, default=DEFAULT_QURAN_TRANSLATION_PATH)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--arabic-source-id", default=DEFAULT_QURAN_TEXT_WORK_SOURCE_ID)
    parser.add_argument("--translation-source-id", default=DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID)
    parser.add_argument("--echo", action="store_true")
    return parser.parse_args()



def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))



def _infer_translation_seed(rows: list[dict[str, str]], *, source_id: str):
    first = rows[0] if rows else {}
    return build_translation_work_seed(
        source_id=source_id,
        translation_name=str(first.get("translation_name") or "Quran translation").strip(),
        translator=str(first.get("translator") or "").strip(),
        language=str(first.get("language") or "en").strip() or "en",
        source_name=str(first.get("source_name") or "").strip(),
    )



def main() -> None:
    args = parse_args()

    arabic_rows = _read_csv_rows(Path(args.arabic_csv))
    translation_rows = _read_csv_rows(Path(args.translation_csv))
    if len(arabic_rows) != EXPECTED_AYAH_COUNT:
        raise SystemExit(f"Expected {EXPECTED_AYAH_COUNT} Arabic ayah rows, found {len(arabic_rows)}")
    if len(translation_rows) != EXPECTED_AYAH_COUNT:
        raise SystemExit(f"Expected {EXPECTED_AYAH_COUNT} translation ayah rows, found {len(translation_rows)}")

    engine = make_engine(database_url=args.database_url, echo=args.echo)
    Base.metadata.create_all(engine)

    with get_session(database_url=args.database_url, echo=args.echo) as session:
        repo = SqlAlchemyQuranRepository(session)
        surah_counts = repo.upsert_surah_rows(build_surah_rows_from_arabic_csv(args.arabic_csv))
        arabic_counts = repo.upsert_quran_ayah_rows(
            work_source_id=args.arabic_source_id,
            rows=arabic_rows,
            seed=build_arabic_work_seed(args.arabic_source_id),
        )
        translation_counts = repo.upsert_translation_rows(
            work_source_id=args.translation_source_id,
            rows=translation_rows,
            seed=_infer_translation_seed(translation_rows, source_id=args.translation_source_id),
        )

    print(
        {
            "quran_surahs": surah_counts,
            "quran_ayahs": arabic_counts,
            "quran_translation_ayahs": translation_counts,
            "arabic_source_id": args.arabic_source_id,
            "translation_source_id": args.translation_source_id,
        }
    )


if __name__ == "__main__":
    main()
