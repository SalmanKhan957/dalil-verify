from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from domains.ask.workflows.explain_quran_reference import explain_quran_reference
from domains.quran.retrieval.metadata_loader import DEFAULT_QURAN_ARABIC_PATH
from domains.quran.retrieval.translation_fetcher import DEFAULT_QURAN_TRANSLATION_PATH
from domains.tafsir.formatter import build_tafsir_citation
from domains.tafsir.service import TafsirService


def explain_quran_with_tafsir(
    *,
    query: str,
    resolution: dict[str, Any] | None = None,
    include_tafsir: bool = False,
    tafsir_source_id: str = "tafsir:ibn-kathir-en",
    tafsir_limit: int = 3,
    database_url: str | None = None,
    quran_csv_path: str | Path = DEFAULT_QURAN_ARABIC_PATH,
    translation_csv_path: str | Path = DEFAULT_QURAN_TRANSLATION_PATH,
) -> dict[str, Any]:
    base_result = explain_quran_reference(
        query,
        resolution=resolution,
        quran_csv_path=quran_csv_path,
        translation_csv_path=translation_csv_path,
    )

    response: dict[str, Any] = {
        **base_result,
        "tafsir": [],
        "tafsir_source_id": tafsir_source_id if include_tafsir else None,
        "tafsir_error": None,
    }

    if not include_tafsir:
        return response

    if not base_result.get("ok"):
        response["tafsir_error"] = "tafsir_skipped_due_to_quran_resolution_failure"
        return response

    quran_span = base_result.get("quran_span") or {}
    if not quran_span:
        response["tafsir_error"] = "tafsir_skipped_due_to_missing_quran_span"
        return response

    try:
        tafsir_service = TafsirService(database_url=database_url)
        hits = tafsir_service.get_overlap_for_quran_span(
            source_id=tafsir_source_id,
            surah_no=int(quran_span["surah_no"]),
            ayah_start=int(quran_span["ayah_start"]),
            ayah_end=int(quran_span["ayah_end"]),
            limit=int(tafsir_limit),
        )
    except (PermissionError, LookupError, RuntimeError, ValueError) as exc:
        response["tafsir_error"] = str(exc)
        return response

    response["tafsir"] = [
        {
            "citation": asdict(build_tafsir_citation(hit)),
            "text_plain": hit.text_plain,
            "text_html": hit.text_html,
            "coverage_mode": hit.coverage_mode,
            "coverage_confidence": float(hit.coverage_confidence),
            "surah_no": hit.surah_no,
            "ayah_start": hit.ayah_start,
            "ayah_end": hit.ayah_end,
            "anchor_verse_key": hit.anchor_verse_key,
            "quran_span_ref": hit.quran_span_ref,
        }
        for hit in hits
    ]
    return response
