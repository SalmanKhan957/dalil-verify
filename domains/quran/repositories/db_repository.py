from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from domains.quran.citations.surah_aliases import SURAH_CANONICAL_NAMES
from infrastructure.db.models.quran_ayah import QuranAyahORM
from infrastructure.db.models.quran_surah import QuranSurahORM
from infrastructure.db.models.quran_translation_ayah import QuranTranslationAyahORM
from infrastructure.db.models.source_work import SourceWorkORM
from infrastructure.db.session import get_session

DEFAULT_QURAN_TEXT_WORK_SOURCE_ID = "quran:tanzil-simple"
DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID = "quran:towards-understanding-en"
DEFAULT_QURAN_REPOSITORY_MODE = "csv"
VALID_QURAN_REPOSITORY_MODES = {"csv", "db_preferred", "db_only"}
DEFAULT_QURAN_DB_METADATA = {
    DEFAULT_QURAN_TEXT_WORK_SOURCE_ID: {
        "display_name": "Quran Arabic Canonical Text (Simple)",
        "citation_label": "Quran",
        "author_name": None,
        "language_code": "ar",
        "source_kind": "canonical_text",
        "work_slug": "tanzil-simple",
        "upstream_provider": "dalil_bootstrap",
        "upstream_resource_id": None,
        "enabled": True,
        "approved_for_answering": True,
        "metadata_json": {"ingested_from": "quran_arabic_canonical.csv"},
    },
    DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID: {
        "display_name": "Towards Understanding the Quran",
        "citation_label": "Towards Understanding the Quran",
        "author_name": "Abul Ala Maududi",
        "language_code": "en",
        "source_kind": "translation",
        "work_slug": "towards-understanding-en",
        "upstream_provider": "dalil_bootstrap",
        "upstream_resource_id": None,
        "enabled": True,
        "approved_for_answering": True,
        "metadata_json": {"source_name": "tanzil_local_file", "ingested_from": "quran_en_single_translation.csv"},
    },
}


class QuranRepositoryUnavailable(RuntimeError):
    """Raised when the canonical Quran DB repository cannot satisfy a request."""


@dataclass(frozen=True)
class QuranWorkSeed:
    source_id: str
    display_name: str
    citation_label: str
    language_code: str
    source_kind: str
    author_name: str | None = None
    work_slug: str | None = None
    upstream_provider: str = "dalil_bootstrap"
    upstream_resource_id: int | None = None
    enabled: bool = True
    approved_for_answering: bool = True
    metadata_json: dict[str, Any] | None = None



def resolve_quran_repository_mode(mode: str | None = None) -> str:
    resolved = (mode or os.getenv("DALIL_QURAN_REPOSITORY_MODE") or DEFAULT_QURAN_REPOSITORY_MODE).strip().lower()
    if resolved not in VALID_QURAN_REPOSITORY_MODES:
        return DEFAULT_QURAN_REPOSITORY_MODE
    return resolved



def should_use_database(mode: str | None = None) -> bool:
    return resolve_quran_repository_mode(mode) in {"db_preferred", "db_only"}



def is_database_required(mode: str | None = None) -> bool:
    return resolve_quran_repository_mode(mode) == "db_only"



def _derive_work_slug(source_id: str) -> str:
    _, _, slug = source_id.partition(":")
    return slug.replace(":", "-") or source_id.replace(":", "-")



def _default_seed_for_source_id(source_id: str) -> QuranWorkSeed:
    defaults = DEFAULT_QURAN_DB_METADATA.get(source_id)
    if defaults is None:
        raise ValueError(f"No default Quran work metadata registered for source_id={source_id}")
    return QuranWorkSeed(source_id=source_id, **defaults)



def _ensure_source_work(session: Session, seed: QuranWorkSeed) -> SourceWorkORM:
    row = session.execute(select(SourceWorkORM).where(SourceWorkORM.source_id == seed.source_id)).scalar_one_or_none()
    values = {
        "source_domain": "quran",
        "work_slug": seed.work_slug or _derive_work_slug(seed.source_id),
        "source_id": seed.source_id,
        "display_name": seed.display_name,
        "citation_label": seed.citation_label,
        "author_name": seed.author_name,
        "language_code": seed.language_code,
        "source_kind": seed.source_kind,
        "upstream_provider": seed.upstream_provider,
        "upstream_resource_id": seed.upstream_resource_id,
        "enabled": seed.enabled,
        "approved_for_answering": seed.approved_for_answering,
        "default_for_explain": False,
        "supports_quran_composition": False,
        "priority_rank": 10 if seed.source_kind == "canonical_text" else 20,
        "version_label": None,
        "policy_note": None,
        "metadata_json": seed.metadata_json or {},
    }
    if row is None:
        row = SourceWorkORM(**values)
        session.add(row)
        session.flush()
        return row

    changed = False
    for field, value in values.items():
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed = True
    if changed:
        session.flush()
    return row


class SqlAlchemyQuranRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_work(self, seed: QuranWorkSeed) -> SourceWorkORM:
        return _ensure_source_work(self.session, seed)

    def upsert_surah_rows(self, rows: Iterable[dict[str, Any]]) -> dict[str, int]:
        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        for row in rows:
            surah_no = int(row["surah_no"])
            existing = self.session.get(QuranSurahORM, surah_no)
            values = {
                "surah_no": surah_no,
                "surah_name_ar": str(row.get("surah_name_ar") or "").strip(),
                "surah_name_en": str(row.get("surah_name_en") or SURAH_CANONICAL_NAMES.get(surah_no, "")).strip(),
                "ayah_count": int(row.get("ayah_count") or 0),
            }
            if existing is None:
                self.session.add(QuranSurahORM(**values))
                counts["inserted"] += 1
                continue
            changed = False
            for field, value in values.items():
                if getattr(existing, field) != value:
                    setattr(existing, field, value)
                    changed = True
            counts["updated"] += int(changed)
            counts["unchanged"] += int(not changed)
        self.session.flush()
        return counts

    def upsert_quran_ayah_rows(self, *, work_source_id: str, rows: Iterable[dict[str, Any]], seed: QuranWorkSeed | None = None) -> dict[str, int]:
        work = self.ensure_work(seed or _default_seed_for_source_id(work_source_id))
        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        for row in rows:
            surah_no = int(row["surah_no"])
            ayah_no = int(row["ayah_no"])
            existing = self.session.execute(
                select(QuranAyahORM).where(
                    QuranAyahORM.work_id == work.id,
                    QuranAyahORM.surah_no == surah_no,
                    QuranAyahORM.ayah_no == ayah_no,
                )
            ).scalar_one_or_none()
            values = {
                "work_id": work.id,
                "surah_no": surah_no,
                "ayah_no": ayah_no,
                "canonical_source_id": str(row.get("canonical_source_id") or f"quran:{surah_no}:{ayah_no}:ar"),
                "citation_string": str(row.get("citation_string") or f"Quran {surah_no}:{ayah_no}"),
                "text_display": str(row.get("text_display") or ""),
                "text_normalized_light": str(row.get("text_normalized_light") or ""),
                "text_normalized_aggressive": str(row.get("text_normalized_aggressive") or ""),
                "bismillah": (str(row.get("bismillah") or "").strip() or None),
            }
            if existing is None:
                self.session.add(QuranAyahORM(**values))
                counts["inserted"] += 1
                continue
            changed = False
            for field, value in values.items():
                if getattr(existing, field) != value:
                    setattr(existing, field, value)
                    changed = True
            counts["updated"] += int(changed)
            counts["unchanged"] += int(not changed)
        self.session.flush()
        return counts

    def upsert_translation_rows(self, *, work_source_id: str, rows: Iterable[dict[str, Any]], seed: QuranWorkSeed | None = None) -> dict[str, int]:
        work = self.ensure_work(seed or _default_seed_for_source_id(work_source_id))
        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        for row in rows:
            surah_no = int(row["surah_no"])
            ayah_no = int(row["ayah_no"])
            existing = self.session.execute(
                select(QuranTranslationAyahORM).where(
                    QuranTranslationAyahORM.work_id == work.id,
                    QuranTranslationAyahORM.surah_no == surah_no,
                    QuranTranslationAyahORM.ayah_no == ayah_no,
                )
            ).scalar_one_or_none()
            values = {
                "work_id": work.id,
                "surah_no": surah_no,
                "ayah_no": ayah_no,
                "text_display": str(row.get("text_display") or row.get("text") or ""),
                "text_raw_html": (str(row.get("text_raw_html") or "").strip() or None),
                "translation_name": (str(row.get("translation_name") or "").strip() or None),
                "translator": (str(row.get("translator") or "").strip() or None),
                "language_code": str(row.get("language") or row.get("language_code") or work.language_code or "en"),
            }
            if existing is None:
                self.session.add(QuranTranslationAyahORM(**values))
                counts["inserted"] += 1
                continue
            changed = False
            for field, value in values.items():
                if getattr(existing, field) != value:
                    setattr(existing, field, value)
                    changed = True
            counts["updated"] += int(changed)
            counts["unchanged"] += int(not changed)
        self.session.flush()
        return counts

    def load_quran_metadata(self, *, work_source_id: str = DEFAULT_QURAN_TEXT_WORK_SOURCE_ID) -> dict[int, dict[str, Any]]:
        work = self._get_work(work_source_id)
        rows = self.session.execute(select(QuranSurahORM).order_by(QuranSurahORM.surah_no)).scalars().all()
        if not rows:
            raise LookupError("No canonical Quran surah metadata found in database")
        return {
            int(row.surah_no): {
                "surah_no": int(row.surah_no),
                "ayah_count": int(row.ayah_count),
                "surah_name_ar": row.surah_name_ar,
                "surah_name_en": row.surah_name_en,
                "source_type": "quran",
                "work_source_id": work.source_id,
            }
            for row in rows
        }

    def fetch_quran_span(
        self,
        *,
        surah_no: int,
        ayah_start: int,
        ayah_end: int,
        work_source_id: str = DEFAULT_QURAN_TEXT_WORK_SOURCE_ID,
    ) -> list[dict[str, Any]]:
        work = self._get_work(work_source_id)
        rows = self.session.execute(
            select(QuranAyahORM)
            .where(
                QuranAyahORM.work_id == work.id,
                QuranAyahORM.surah_no == int(surah_no),
                QuranAyahORM.ayah_no >= int(ayah_start),
                QuranAyahORM.ayah_no <= int(ayah_end),
            )
            .order_by(QuranAyahORM.ayah_no)
        ).scalars().all()
        expected = int(ayah_end) - int(ayah_start) + 1
        if len(rows) != expected:
            raise LookupError(f"Canonical Quran DB rows missing for span {surah_no}:{ayah_start}-{ayah_end}")
        return [
            {
                "surah_no": int(row.surah_no),
                "ayah_no": int(row.ayah_no),
                "citation_string": row.citation_string,
                "canonical_source_id": row.canonical_source_id,
                "text_display": row.text_display,
                "text_normalized_light": row.text_normalized_light,
                "text_normalized_aggressive": row.text_normalized_aggressive,
                "bismillah": row.bismillah or "",
                "source_id": work.source_id,
                "translation_name": work.display_name,
            }
            for row in rows
        ]

    def fetch_translation_span(
        self,
        *,
        surah_no: int,
        ayah_start: int,
        ayah_end: int,
        work_source_id: str = DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID,
    ) -> dict[str, Any]:
        work = self._get_work(work_source_id)
        rows = self.session.execute(
            select(QuranTranslationAyahORM)
            .where(
                QuranTranslationAyahORM.work_id == work.id,
                QuranTranslationAyahORM.surah_no == int(surah_no),
                QuranTranslationAyahORM.ayah_no >= int(ayah_start),
                QuranTranslationAyahORM.ayah_no <= int(ayah_end),
            )
            .order_by(QuranTranslationAyahORM.ayah_no)
        ).scalars().all()
        expected = int(ayah_end) - int(ayah_start) + 1
        if len(rows) != expected:
            raise LookupError(f"Canonical Quran translation DB rows missing for span {surah_no}:{ayah_start}-{ayah_end}")

        structured_rows = []
        for row in rows:
            structured_rows.append(
                {
                    "surah_no": int(row.surah_no),
                    "ayah_no": int(row.ayah_no),
                    "text_display": row.text_display,
                    "text_raw_html": row.text_raw_html or row.text_display,
                    "translation_name": row.translation_name or work.display_name,
                    "translator": row.translator or work.author_name or "",
                    "language": row.language_code or work.language_code,
                    "source_id": work.source_id,
                    "source_name": (work.metadata_json or {}).get("source_name") or work.display_name,
                }
            )

        return {
            "language": work.language_code,
            "translation_name": structured_rows[0].get("translation_name") or work.display_name,
            "translator": structured_rows[0].get("translator") or work.author_name or "",
            "source_id": work.source_id,
            "source_name": (work.metadata_json or {}).get("source_name") or work.display_name,
            "text": " ".join(row["text_display"].strip() for row in structured_rows if row.get("text_display")).strip(),
            "rows": structured_rows,
        }

    def _get_work(self, source_id: str) -> SourceWorkORM:
        row = self.session.execute(select(SourceWorkORM).where(SourceWorkORM.source_id == source_id)).scalar_one_or_none()
        if row is None:
            raise LookupError(f"Canonical Quran source work not found for source_id={source_id}")
        return row



def _read_csv_rows(csv_path: str | Path) -> list[dict[str, str]]:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))



def build_surah_rows_from_arabic_csv(csv_path: str | Path) -> list[dict[str, Any]]:
    rows = _read_csv_rows(csv_path)
    metadata: dict[int, dict[str, Any]] = {}
    for row in rows:
        surah_no = int(row["surah_no"])
        ayah_no = int(row["ayah_no"])
        entry = metadata.setdefault(
            surah_no,
            {
                "surah_no": surah_no,
                "surah_name_ar": str(row.get("surah_name_ar") or "").strip(),
                "surah_name_en": SURAH_CANONICAL_NAMES.get(surah_no, ""),
                "ayah_count": 0,
            },
        )
        entry["ayah_count"] = max(int(entry["ayah_count"]), ayah_no)
    return [metadata[surah_no] for surah_no in sorted(metadata)]



def build_arabic_work_seed(source_id: str = DEFAULT_QURAN_TEXT_WORK_SOURCE_ID) -> QuranWorkSeed:
    defaults = DEFAULT_QURAN_DB_METADATA.get(source_id)
    if defaults is not None:
        return _default_seed_for_source_id(source_id)
    return QuranWorkSeed(
        source_id=source_id,
        display_name="Quran Arabic Canonical Text",
        citation_label="Quran",
        author_name=None,
        language_code="ar",
        source_kind="canonical_text",
        work_slug=_derive_work_slug(source_id),
        upstream_provider="dalil_bootstrap",
        upstream_resource_id=None,
        enabled=True,
        approved_for_answering=True,
        metadata_json={"ingested_from": "quran_arabic_canonical.csv"},
    )



def build_translation_work_seed(
    *,
    source_id: str = DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID,
    translation_name: str,
    translator: str = "",
    language: str = "en",
    source_name: str = "",
) -> QuranWorkSeed:
    defaults = DEFAULT_QURAN_DB_METADATA.get(source_id)
    metadata_json = dict((defaults or {}).get("metadata_json") or {})
    if source_name:
        metadata_json["source_name"] = source_name
    return QuranWorkSeed(
        source_id=source_id,
        display_name=translation_name,
        citation_label=translation_name,
        author_name=translator or None,
        language_code=language,
        source_kind="translation",
        work_slug=(defaults or {}).get("work_slug") or _derive_work_slug(source_id),
        upstream_provider=(defaults or {}).get("upstream_provider") or "dalil_bootstrap",
        upstream_resource_id=(defaults or {}).get("upstream_resource_id"),
        enabled=True,
        approved_for_answering=True,
        metadata_json=metadata_json,
    )



def load_quran_metadata_from_db(
    *,
    database_url: str | None = None,
    work_source_id: str = DEFAULT_QURAN_TEXT_WORK_SOURCE_ID,
) -> dict[int, dict[str, Any]]:
    try:
        with get_session(database_url=database_url) as session:
            repo = SqlAlchemyQuranRepository(session)
            return repo.load_quran_metadata(work_source_id=work_source_id)
    except (RuntimeError, LookupError, OperationalError, SQLAlchemyError) as exc:
        raise QuranRepositoryUnavailable(str(exc)) from exc



def lookup_quran_span_from_db(
    *,
    surah_no: int,
    ayah_start: int,
    ayah_end: int,
    database_url: str | None = None,
    work_source_id: str = DEFAULT_QURAN_TEXT_WORK_SOURCE_ID,
) -> list[dict[str, Any]]:
    try:
        with get_session(database_url=database_url) as session:
            repo = SqlAlchemyQuranRepository(session)
            return repo.fetch_quran_span(
                surah_no=surah_no,
                ayah_start=ayah_start,
                ayah_end=ayah_end,
                work_source_id=work_source_id,
            )
    except (RuntimeError, LookupError, OperationalError, SQLAlchemyError) as exc:
        raise QuranRepositoryUnavailable(str(exc)) from exc



def fetch_translation_span_from_db(
    *,
    surah_no: int,
    ayah_start: int,
    ayah_end: int,
    database_url: str | None = None,
    work_source_id: str = DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID,
) -> dict[str, Any]:
    try:
        with get_session(database_url=database_url) as session:
            repo = SqlAlchemyQuranRepository(session)
            return repo.fetch_translation_span(
                surah_no=surah_no,
                ayah_start=ayah_start,
                ayah_end=ayah_end,
                work_source_id=work_source_id,
            )
    except (RuntimeError, LookupError, OperationalError, SQLAlchemyError) as exc:
        raise QuranRepositoryUnavailable(str(exc)) from exc
