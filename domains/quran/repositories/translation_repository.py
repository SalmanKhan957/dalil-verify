from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_QURAN_TRANSLATION_PATH = REPO_ROOT / "data/processed/quran_translations/quran_en_single_translation.csv"


@lru_cache(maxsize=4)
def load_translation_row_index(
    csv_path: str | Path = DEFAULT_QURAN_TRANSLATION_PATH,
) -> dict[tuple[int, int], dict[str, Any]]:
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


@lru_cache(maxsize=4)
def load_english_translation_map(csv_path: Path | None) -> tuple[dict[tuple[int, int], dict[str, Any]], dict[str, Any]]:
    if csv_path is None or not csv_path.exists():
        return {}, {"loaded": False, "row_count": 0, "path": str(csv_path) if csv_path else None}

    rows: dict[tuple[int, int], dict[str, Any]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            surah_no = int(row["surah_no"])
            ayah_no = int(row["ayah_no"])
            rows[(surah_no, ayah_no)] = {
                "surah_no": surah_no,
                "ayah_no": ayah_no,
                "text": row.get("text_display") or row.get("translation_text") or row.get("text") or "",
                "translation_name": row.get("translation_name") or row.get("translator") or "",
                "language": row.get("language") or "en",
                "source_id": row.get("source_id") or "",
            }

    return rows, {"loaded": True, "row_count": len(rows), "path": str(csv_path)}


def fetch_translation_span(
    *,
    surah_no: int,
    ayah_start: int,
    ayah_end: int,
    csv_path: str | Path = DEFAULT_QURAN_TRANSLATION_PATH,
) -> dict[str, Any]:
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


def attach_english_translation(best_match: dict[str, Any] | None, en_map: dict[tuple[int, int], dict[str, Any]]) -> dict[str, Any] | None:
    if not best_match or not en_map:
        return best_match

    enriched = dict(best_match)
    source_type = enriched.get("source_type")

    if source_type == "quran" and enriched.get("ayah_no") is not None:
        key = (int(enriched["surah_no"]), int(enriched["ayah_no"]))
        translation = en_map.get(key)
        if translation:
            enriched["english_translation"] = {
                "translation_name": translation.get("translation_name"),
                "text": translation.get("text"),
                "ayah_keys": [f"{translation['surah_no']}:{translation['ayah_no']}"]
            }
        return enriched

    start_ayah = enriched.get("start_ayah")
    end_ayah = enriched.get("end_ayah")
    surah_no = enriched.get("surah_no")
    if source_type == "quran_passage" and start_ayah is not None and end_ayah is not None and surah_no is not None:
        components = []
        texts = []
        translation_name = ""
        for ayah_no in range(int(start_ayah), int(end_ayah) + 1):
            translation = en_map.get((int(surah_no), ayah_no))
            if not translation:
                continue
            if not translation_name:
                translation_name = translation.get("translation_name") or ""
            components.append(
                {
                    "surah_no": int(surah_no),
                    "ayah_no": ayah_no,
                    "text": translation.get("text"),
                }
            )
            texts.append(translation.get("text") or "")

        if components:
            enriched["english_translation"] = {
                "translation_name": translation_name,
                "text": " ".join([t for t in texts if t]).strip(),
                "ayah_keys": [f"{int(surah_no)}:{item['ayah_no']}" for item in components],
                "components": components,
            }

    return enriched
