from __future__ import annotations

from fastapi import Request

from domains.ask.classifier import classify_ask_query
from domains.ask.response_surface import build_ask_response_payload
from domains.ask.workflows.explain_answer import explain_answer


def dispatch_ask_query(
    query: str,
    *,
    request: Request | None = None,
    quran_work_source_id: str | None = None,
    translation_work_source_id: str | None = None,
    debug: bool = False,
) -> dict[str, object]:
    route = classify_ask_query(query)
    result = explain_answer(
        query=query,
        request=request,
        route=route,
        include_tafsir=None,
        quran_work_source_id=quran_work_source_id,
        translation_work_source_id=translation_work_source_id,
        debug=debug,
    )
    return build_ask_response_payload(
        query=query,
        route=route,
        result=result,
    )