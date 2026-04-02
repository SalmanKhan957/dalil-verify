# services/citation_resolver/resolver.py

from __future__ import annotations

from typing import Any

from services.citation_resolver.normalizer import normalize_reference_text
from services.citation_resolver.quran_reference_parser import parse_quran_reference
from shared.schemas.quran_reference import QuranReferenceResolution


def build_canonical_source_id(surah_no: int, ayah_start: int, ayah_end: int) -> str:
    if ayah_start == ayah_end:
        return f"quran:{surah_no}:{ayah_start}"
    return f"quran:{surah_no}:{ayah_start}-{ayah_end}"


def _error_result(
    *,
    normalized_query: str,
    parse_type: str | None,
    error: str,
    surah_no: int | None = None,
    ayah_start: int | None = None,
    ayah_end: int | None = None,
) -> QuranReferenceResolution:
    return QuranReferenceResolution(
        resolved=False,
        source_type="quran",
        resolution_type="explicit_reference",
        canonical_source_id=None,
        surah_no=surah_no,
        ayah_start=ayah_start,
        ayah_end=ayah_end,
        confidence=0.0,
        normalized_query=normalized_query,
        parse_type=parse_type,
        error=error,
    )


def validate_quran_reference(parsed: dict[str, Any], quran_metadata: dict[int, dict[str, Any]]) -> dict[str, Any]:
    surah_no = parsed.get("surah_no")
    ayah_start = parsed.get("ayah_start")
    ayah_end = parsed.get("ayah_end")

    if not isinstance(surah_no, int) or surah_no < 1 or surah_no > 114:
        return {"valid": False, "error": "invalid_surah_number"}

    surah_meta = quran_metadata.get(surah_no)
    if surah_meta is None:
        return {"valid": False, "error": "unknown_surah_metadata"}

    ayah_count = int(surah_meta.get("ayah_count") or 0)
    if ayah_count <= 0:
        return {"valid": False, "error": "invalid_surah_metadata"}

    # Whole surah request: fill the full range here.
    if ayah_start is None and ayah_end is None:
        return {
            "valid": True,
            "surah_no": surah_no,
            "ayah_start": 1,
            "ayah_end": ayah_count,
        }

    if ayah_start is None or ayah_end is None:
        return {"valid": False, "error": "incomplete_ayah_range"}

    if ayah_start < 1 or ayah_end < 1:
        return {"valid": False, "error": "invalid_ayah_range"}

    if ayah_end < ayah_start:
        return {"valid": False, "error": "reversed_ayah_range"}

    if ayah_start > ayah_count or ayah_end > ayah_count:
        return {"valid": False, "error": "invalid_ayah_range"}

    return {
        "valid": True,
        "surah_no": surah_no,
        "ayah_start": ayah_start,
        "ayah_end": ayah_end,
    }


def resolve_quran_reference(query: str, quran_metadata: dict[int, dict[str, Any]] | None = None) -> dict[str, Any]:
    """
    Deterministic Quran citation resolver.

    This is NOT quote verification.
    It only resolves explicit references and surah names.
    """
    metadata = quran_metadata or {}
    normalized_query = normalize_reference_text(query)

    if not normalized_query:
        return _error_result(
            normalized_query="",
            parse_type=None,
            error="empty_query",
        ).to_dict()

    parsed = parse_quran_reference(normalized_query)
    if parsed is None:
        return _error_result(
            normalized_query=normalized_query,
            parse_type=None,
            error="could_not_parse_reference",
        ).to_dict()

    validation = validate_quran_reference(parsed, metadata)
    if not validation.get("valid"):
        return _error_result(
            normalized_query=normalized_query,
            parse_type=parsed.get("parse_type"),
            error=validation["error"],
            surah_no=parsed.get("surah_no"),
            ayah_start=parsed.get("ayah_start"),
            ayah_end=parsed.get("ayah_end"),
        ).to_dict()

    surah_no = int(validation["surah_no"])
    ayah_start = int(validation["ayah_start"])
    ayah_end = int(validation["ayah_end"])
    canonical_source_id = build_canonical_source_id(surah_no, ayah_start, ayah_end)

    result = QuranReferenceResolution(
        resolved=True,
        source_type="quran",
        resolution_type="explicit_reference",
        canonical_source_id=canonical_source_id,
        surah_no=surah_no,
        ayah_start=ayah_start,
        ayah_end=ayah_end,
        confidence=1.0,
        normalized_query=normalized_query,
        parse_type=parsed.get("parse_type"),
        error=None,
    )
    return result.to_dict()