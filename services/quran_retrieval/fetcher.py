from __future__ import annotations

from pathlib import Path
from typing import Any

from services.citation_resolver.resolver import build_canonical_source_id
from services.quran_retrieval.metadata_loader import DEFAULT_QURAN_ARABIC_PATH, load_quran_metadata
from services.quran_retrieval.span_lookup import lookup_quran_span
from services.quran_retrieval.translation_fetcher import (
    DEFAULT_QURAN_TRANSLATION_PATH,
    fetch_translation_span,
)


def build_citation_string(surah_no: int, ayah_start: int, ayah_end: int) -> str:
    if ayah_start == ayah_end:
        return f"Quran {surah_no}:{ayah_start}"
    return f"Quran {surah_no}:{ayah_start}-{ayah_end}"


def fetch_quran_span(
    *,
    surah_no: int,
    ayah_start: int,
    ayah_end: int,
    metadata: dict[int, dict[str, Any]] | None = None,
    quran_csv_path: str | Path = DEFAULT_QURAN_ARABIC_PATH,
    translation_csv_path: str | Path = DEFAULT_QURAN_TRANSLATION_PATH,
) -> dict[str, Any]:
    """Fetch a deterministic Quran span with Arabic rows and English translation."""
    meta = metadata or load_quran_metadata(quran_csv_path)
    surah_meta = meta.get(int(surah_no))
    if surah_meta is None:
        raise KeyError(f"Unknown surah metadata for surah {surah_no}")

    arabic_rows = lookup_quran_span(
        surah_no=int(surah_no),
        ayah_start=int(ayah_start),
        ayah_end=int(ayah_end),
        csv_path=quran_csv_path,
    )
    translation = fetch_translation_span(
        surah_no=int(surah_no),
        ayah_start=int(ayah_start),
        ayah_end=int(ayah_end),
        csv_path=translation_csv_path,
    )

    ayah_rows: list[dict[str, Any]] = []
    for arabic_row, translation_row in zip(arabic_rows, translation["rows"], strict=True):
        ayah_rows.append(
            {
                "surah_no": int(arabic_row["surah_no"]),
                "ayah_no": int(arabic_row["ayah_no"]),
                "citation_string": arabic_row.get("citation_string") or f"Quran {arabic_row['surah_no']}:{arabic_row['ayah_no']}",
                "arabic_text": arabic_row.get("text_display") or "",
                "arabic_canonical_source_id": arabic_row.get("canonical_source_id") or "",
                "translation_text": translation_row.get("text_display") or "",
                "translation_source_id": translation_row.get("source_id") or "",
            }
        )

    return {
        "source_type": "quran_span",
        "canonical_source_id": build_canonical_source_id(int(surah_no), int(ayah_start), int(ayah_end)),
        "citation_string": build_citation_string(int(surah_no), int(ayah_start), int(ayah_end)),
        "surah_no": int(surah_no),
        "ayah_start": int(ayah_start),
        "ayah_end": int(ayah_end),
        "surah_name_ar": surah_meta.get("surah_name_ar") or "",
        "surah_name_en": surah_meta.get("surah_name_en") or "",
        "ayah_count_in_surah": int(surah_meta.get("ayah_count") or 0),
        "arabic_text": " ".join((row.get("text_display") or "").strip() for row in arabic_rows if row.get("text_display")).strip(),
        "translation": {
            "language": translation.get("language") or "en",
            "translation_name": translation.get("translation_name") or "",
            "translator": translation.get("translator") or "",
            "source_id": translation.get("source_id") or "",
            "source_name": translation.get("source_name") or "",
            "text": translation.get("text") or "",
        },
        "ayah_rows": ayah_rows,
    }
