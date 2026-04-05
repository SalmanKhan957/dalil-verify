from __future__ import annotations

from fastapi import APIRouter, Request

from apps.ask_api.schemas import ExplainAnswerResponse, ExplainQuranReferenceRequest
from domains.ask.dispatcher import dispatch_ask_query
from domains.ask.response_surface import build_explain_response_payload_from_ask_payload

router = APIRouter(prefix="/ask", tags=["ask"])


def explain_answer(
    *,
    query: str,
    request: Request | None = None,
    include_tafsir: bool | None = None,
    tafsir_source_id: str | None = None,
    tafsir_limit: int = 3,
    quran_work_source_id: str | None = None,
    translation_work_source_id: str | None = None,
    quran_text_source_requested: bool = False,
    quran_translation_source_requested: bool = False,
    debug: bool = False,
) -> dict[str, object]:
    ask_payload = dispatch_ask_query(
        query,
        request=request,
        include_tafsir=(include_tafsir if include_tafsir is not None else True),
        tafsir_source_id=tafsir_source_id,
        tafsir_limit=tafsir_limit,
        quran_work_source_id=quran_work_source_id,
        translation_work_source_id=translation_work_source_id,
        quran_text_source_requested=quran_text_source_requested,
        quran_translation_source_requested=quran_translation_source_requested,
        debug=debug,
    )
    return build_explain_response_payload_from_ask_payload(ask_payload)


@router.post("/explain", response_model=ExplainAnswerResponse)
def explain_reference(payload: ExplainQuranReferenceRequest, request: Request) -> ExplainAnswerResponse:
    result = explain_answer(
        query=payload.query,
        request=request,
        include_tafsir=payload.include_tafsir,
        tafsir_source_id=payload.tafsir_source_id,
        tafsir_limit=payload.tafsir_limit,
        quran_work_source_id=payload.quran_text_source_id,
        translation_work_source_id=payload.quran_translation_source_id,
        quran_text_source_requested=payload.quran_text_source_id is not None,
        quran_translation_source_requested=payload.quran_translation_source_id is not None,
        debug=payload.debug,
    )
    return ExplainAnswerResponse(**result)
