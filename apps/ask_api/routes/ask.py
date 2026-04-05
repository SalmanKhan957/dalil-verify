from __future__ import annotations

from fastapi import APIRouter, Request

from apps.ask_api.schemas import AskRequest, AskResponse
from domains.ask.dispatcher import dispatch_ask_query

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("", response_model=AskResponse)
def ask(payload: AskRequest, request: Request) -> AskResponse:
    result = dispatch_ask_query(
        payload.query,
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
    return AskResponse(**result)
