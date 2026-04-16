from __future__ import annotations

from fastapi import APIRouter, Request, Response

from apps.ask_api.schemas import ExplainAnswerResponse, ExplainQuranReferenceRequest
from domains.ask.dispatcher import dispatch_ask_query
from domains.ask.response_surface import build_explain_response_payload_from_ask_payload

router = APIRouter(prefix="/ask", tags=["ask"])
_EXPLAIN_DEFAULT_INCLUDE_TAFSIR = True


def _resolve_explain_include_tafsir(include_tafsir: bool | None) -> bool:
    return include_tafsir if include_tafsir is not None else _EXPLAIN_DEFAULT_INCLUDE_TAFSIR


def explain_answer(*, query: str, request: Request | None = None, include_tafsir: bool | None = None, tafsir_source_id: str | None = None, tafsir_limit: int = 3, quran_work_source_id: str | None = None, translation_work_source_id: str | None = None, quran_text_source_requested: bool = False, quran_translation_source_requested: bool = False, hadith_source_id: str | None = None, request_context: dict[str, object] | None = None, request_preferences: dict[str, object] | None = None, source_controls: dict[str, object] | None = None, request_contract_version: str = 'ask.vnext', debug: bool = False,) -> dict[str, object]:
    ask_payload = dispatch_ask_query(
        query,
        request=request,
        include_tafsir=_resolve_explain_include_tafsir(include_tafsir),
        tafsir_source_id=tafsir_source_id,
        tafsir_limit=tafsir_limit,
        quran_work_source_id=quran_work_source_id,
        translation_work_source_id=translation_work_source_id,
        quran_text_source_requested=quran_text_source_requested,
        quran_translation_source_requested=quran_translation_source_requested,
        hadith_source_id=hadith_source_id,
        request_context=request_context,
        request_preferences=request_preferences,
        source_controls=source_controls,
        request_contract_version=request_contract_version,
        debug=debug,
    )
    return build_explain_response_payload_from_ask_payload(ask_payload)


@router.post("/explain", response_model=ExplainAnswerResponse)
def explain(payload: ExplainQuranReferenceRequest, request: Request, response: Response) -> ExplainAnswerResponse:
    response_payload = explain_answer(
        query=payload.query,
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
    orchestration = response_payload.get('orchestration')
    if isinstance(orchestration, dict):
        diagnostics = orchestration.get('diagnostics')
        if isinstance(diagnostics, dict) and diagnostics.get('request_id'):
            response.headers['X-Dalil-Request-Id'] = str(diagnostics['request_id'])
    return ExplainAnswerResponse(**response_payload)
