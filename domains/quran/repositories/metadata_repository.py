from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

from domains.quran.citations.surah_aliases import SURAH_CANONICAL_NAMES

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_QURAN_ARABIC_PATH = REPO_ROOT / "data/processed/quran/quran_arabic_canonical.csv"


@lru_cache(maxsize=4)
def load_quran_metadata(csv_path: str | Path = DEFAULT_QURAN_ARABIC_PATH) -> dict[int, dict[str, Any]]:
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
