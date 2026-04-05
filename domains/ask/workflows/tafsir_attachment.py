from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable


TafsirServiceFactory = Callable[..., Any]
TafsirCitationBuilder = Callable[[Any], Any]


def attach_tafsir_to_quran_result(
    base_result: dict[str, Any],
    *,
    include_tafsir: bool,
    tafsir_source_id: str,
    tafsir_limit: int,
    database_url: str | None,
    tafsir_service_factory: TafsirServiceFactory,
    citation_builder: TafsirCitationBuilder,
) -> dict[str, Any]:
    """Attach governed Tafsir support to a resolved Quran response.

    This helper keeps the Quran+Tafsir shaping logic in one place while letting
    both the domain workflow and the legacy service workflow preserve their own
    dependency seams.
    """
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
        tafsir_service = tafsir_service_factory(database_url=database_url)
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
            "citation": asdict(citation_builder(hit)),
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
