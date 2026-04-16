from __future__ import annotations

from fastapi import APIRouter, Request, Response

from apps.ask_api.schemas import AskRequest, AskResponse
from domains.ask.dispatcher import dispatch_ask_query

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("", response_model=AskResponse)
def ask(payload: AskRequest, request: Request, response: Response) -> AskResponse:
    result = dispatch_ask_query(
        payload.query,
        request=request,
        include_tafsir=payload.effective_include_tafsir,
        tafsir_source_id=payload.effective_tafsir_source_id,
        tafsir_limit=payload.effective_tafsir_limit,
        quran_work_source_id=payload.effective_quran_text_source_id,
        translation_work_source_id=payload.effective_quran_translation_source_id,
        quran_text_source_requested=payload.effective_quran_text_source_id is not None,
        quran_translation_source_requested=payload.effective_quran_translation_source_id is not None,
        hadith_source_id=payload.effective_hadith_source_id,
        request_context=payload.request_context_payload,
        request_preferences=payload.request_preferences_payload,
        source_controls=payload.source_controls_payload,
        request_contract_version=payload.request_contract_version,
        debug=payload.effective_debug,
    )
    request_id = None
    orchestration = result.get('orchestration')
    if isinstance(orchestration, dict):
        diagnostics = orchestration.get('diagnostics')
        if isinstance(diagnostics, dict):
            request_id = diagnostics.get('request_id')
    if request_id:
        response.headers['X-Dalil-Request-Id'] = str(request_id)
    return AskResponse(**result)
