from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

from domains.quran.citations.surah_aliases import SURAH_CANONICAL_NAMES
from domains.quran.repositories.db_repository import (
    DEFAULT_QURAN_TEXT_WORK_SOURCE_ID,
    QuranRepositoryUnavailable,
    is_database_required,
    load_quran_metadata_from_db,
    should_use_database,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_QURAN_ARABIC_PATH = REPO_ROOT / "data/processed/quran/quran_arabic_canonical.csv"


@lru_cache(maxsize=4)
def _load_quran_metadata_from_csv(csv_path: str | Path = DEFAULT_QURAN_ARABIC_PATH) -> dict[int, dict[str, Any]]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Quran Arabic corpus not found at: {path}")

    metadata: dict[int, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            surah_no = int(row["surah_no"])
            ayah_no = int(row["ayah_no"])
            entry = metadata.setdefault(
                surah_no,
                {
                    "surah_no": surah_no,
                    "ayah_count": 0,
                    "surah_name_ar": row.get("surah_name_ar") or "",
                    "surah_name_en": SURAH_CANONICAL_NAMES.get(surah_no, ""),
                    "source_type": "quran",
                },
            )
            entry["ayah_count"] = max(int(entry["ayah_count"]), ayah_no)
            if not entry.get("surah_name_ar"):
                entry["surah_name_ar"] = row.get("surah_name_ar") or ""

    return metadata



def load_quran_metadata(
    csv_path: str | Path = DEFAULT_QURAN_ARABIC_PATH,
    *,
    repository_mode: str | None = None,
    database_url: str | None = None,
    work_source_id: str = DEFAULT_QURAN_TEXT_WORK_SOURCE_ID,
) -> dict[int, dict[str, Any]]:
    if should_use_database(repository_mode):
        try:
            return load_quran_metadata_from_db(database_url=database_url, work_source_id=work_source_id)
        except QuranRepositoryUnavailable:
            if is_database_required(repository_mode):
                raise
    return _load_quran_metadata_from_csv(csv_path)
