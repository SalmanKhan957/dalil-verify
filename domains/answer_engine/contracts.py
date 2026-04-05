from __future__ import annotations

from typing import Any

from shared.schemas.source_citation import SourceCitation


def make_explain_answer_payload(
    *,
    ok: bool,
    query: str,
    answer_mode: str,
    route_type: str,
    action_type: str,
    answer_text: str | None,
    citations: list[SourceCitation],
    quran_support: dict[str, Any] | None,
    tafsir_support: list[dict[str, Any]],
    resolution: dict[str, Any] | None,
    partial_success: bool,
    warnings: list[str],
    debug: dict[str, Any] | None,
    error: str | None,
    quran_source_selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "query": query,
        "answer_mode": answer_mode,
        "route_type": route_type,
        "action_type": action_type,
        "answer_text": answer_text,
        "citations": [citation.model_dump() for citation in citations],
        "quran_support": quran_support,
        "tafsir_support": tafsir_support,
        "resolution": resolution,
        "partial_success": partial_success,
        "warnings": warnings,
        "debug": debug,
        "error": error,
        "quran_source_selection": quran_source_selection,
    }
