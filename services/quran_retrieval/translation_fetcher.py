from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QURAN_TRANSLATION_PATH = REPO_ROOT / "data/processed/quran_translations/quran_en_single_translation.csv"


@lru_cache(maxsize=4)
def load_translation_row_index(
    csv_path: str | Path = DEFAULT_QURAN_TRANSLATION_PATH,
) -> dict[tuple[int, int], dict[str, Any]]:
    """Load the current runtime English translation corpus."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Quran translation corpus not found at: {path}")

    index: dict[tuple[int, int], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            surah_no = int(row["surah_no"])
            ayah_no = int(row["ayah_no"])
            normalized = dict(row)
            normalized["surah_no"] = surah_no
            normalized["ayah_no"] = ayah_no
            index[(surah_no, ayah_no)] = normalized

    return index


def fetch_translation_span(
    *,
    surah_no: int,
    ayah_start: int,
    ayah_end: int,
    csv_path: str | Path = DEFAULT_QURAN_TRANSLATION_PATH,
) -> dict[str, Any]:
    """Fetch English translation rows for the requested ayah span."""
    if ayah_end < ayah_start:
        raise ValueError("ayah_end must be greater than or equal to ayah_start")

    index = load_translation_row_index(csv_path)
    rows: list[dict[str, Any]] = []
    translation_name = ""
    translator = ""
    source_id = ""
    source_name = ""

    for ayah_no in range(int(ayah_start), int(ayah_end) + 1):
        row = index.get((int(surah_no), ayah_no))
        if row is None:
            raise KeyError(f"Translation row missing for {surah_no}:{ayah_no}")
        rows.append(dict(row))
        if not translation_name:
            translation_name = row.get("translation_name") or row.get("translator") or ""
        if not translator:
            translator = row.get("translator") or ""
        if not source_id:
            source_id = row.get("source_id") or ""
        if not source_name:
            source_name = row.get("source_name") or ""

    return {
        "language": "en",
        "translation_name": translation_name,
        "translator": translator,
        "source_id": source_id,
        "source_name": source_name,
        "text": " ".join((row.get("text_display") or "").strip() for row in rows if row.get("text_display")).strip(),
        "rows": rows,
    }
