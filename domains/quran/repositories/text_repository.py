from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

from domains.quran.repositories.metadata_repository import DEFAULT_QURAN_ARABIC_PATH


@lru_cache(maxsize=4)
def load_quran_row_index(csv_path: str | Path = DEFAULT_QURAN_ARABIC_PATH) -> dict[int, dict[int, dict[str, Any]]]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Quran Arabic corpus not found at: {path}")

    index: dict[int, dict[int, dict[str, Any]]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            surah_no = int(row["surah_no"])
            ayah_no = int(row["ayah_no"])
            normalized = dict(row)
            normalized["surah_no"] = surah_no
            normalized["ayah_no"] = ayah_no
            index.setdefault(surah_no, {})[ayah_no] = normalized

    return index


def lookup_quran_span(
    *,
    surah_no: int,
    ayah_start: int,
    ayah_end: int,
    csv_path: str | Path = DEFAULT_QURAN_ARABIC_PATH,
) -> list[dict[str, Any]]:
    if ayah_end < ayah_start:
        raise ValueError("ayah_end must be greater than or equal to ayah_start")

    index = load_quran_row_index(csv_path)
    surah_rows = index.get(int(surah_no))
    if surah_rows is None:
        raise KeyError(f"Unknown surah number: {surah_no}")

    rows: list[dict[str, Any]] = []
    for ayah_no in range(int(ayah_start), int(ayah_end) + 1):
        row = surah_rows.get(ayah_no)
        if row is None:
            raise KeyError(f"Quran row missing for {surah_no}:{ayah_no}")
        rows.append(dict(row))

    return rows
