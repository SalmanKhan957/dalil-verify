from __future__ import annotations

from fastapi import APIRouter

from apps.ask_api.schemas import ExplainAnswerResponse, ExplainQuranReferenceRequest
from domains.ask.workflows.explain_answer import explain_answer

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("/explain", response_model=ExplainAnswerResponse)
def explain_reference(payload: ExplainQuranReferenceRequest) -> ExplainAnswerResponse:
    result = explain_answer(
        query=payload.query,
        include_tafsir=(payload.include_tafsir if payload.include_tafsir is not None else True),
        tafsir_source_id=payload.tafsir_source_id,
        tafsir_limit=payload.tafsir_limit,
        quran_work_source_id=payload.quran_text_source_id,
        translation_work_source_id=payload.quran_translation_source_id,
        debug=payload.debug,
    )
    return ExplainAnswerResponse(**result)
