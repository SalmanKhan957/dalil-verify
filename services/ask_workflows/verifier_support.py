from __future__ import annotations

from typing import Any

from fastapi import Request

from services.ask_router.route_types import AskActionType, AskRouteType
from services.quran_retrieval.fetcher import fetch_quran_span
from services.quran_verifier.service import verify_quran_text



def is_verifier_match_usable(verifier_result: dict[str, Any]) -> bool:
    if not verifier_result:
        return False
    if not verifier_result.get("best_match"):
        return False
    status = str(verifier_result.get("match_status") or "").lower()
    if "no reliable" in status or "cannot assess" in status:
        return False
    return True



def build_span_from_verifier_result(verifier_result: dict[str, Any]) -> dict[str, Any] | None:
    best_match = (verifier_result or {}).get("best_match") or {}
    if not best_match:
        return None

    surah_no = best_match.get("surah_no")
    if surah_no is None:
        return None

    start_ayah = best_match.get("ayah_no")
    end_ayah = best_match.get("ayah_no")

    if best_match.get("start_ayah") is not None:
        start_ayah = best_match.get("start_ayah")
        end_ayah = best_match.get("end_ayah")

    if start_ayah is None or end_ayah is None:
        return None

    try:
        return fetch_quran_span(
            surah_no=int(surah_no),
            ayah_start=int(start_ayah),
            ayah_end=int(end_ayah),
        )
    except Exception:
        return None



def run_arabic_quran_quote_workflow(
    query: str,
    *,
    quote_payload: str,
    action_type: str,
    request: Request | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    del request
    try:
        verifier_result = verify_quran_text(quote_payload, debug=debug)
    except Exception as exc:  # pragma: no cover - dependency presence varies by repo stage
        return {
            "ok": False,
            "intent": AskRouteType.ARABIC_QURAN_QUOTE.value,
            "action_type": action_type,
            "query": query,
            "quote_payload": quote_payload,
            "verifier_result": None,
            "quran_span": None,
            "error": f"verifier_workflow_unavailable: {exc}",
        }

    quran_span = None
    if action_type in {
        AskActionType.EXPLAIN.value,
        AskActionType.FETCH_TEXT.value,
        AskActionType.VERIFY_THEN_EXPLAIN.value,
    } and is_verifier_match_usable(verifier_result):
        quran_span = build_span_from_verifier_result(verifier_result)

    return {
        "ok": True,
        "intent": AskRouteType.ARABIC_QURAN_QUOTE.value,
        "action_type": action_type,
        "query": query,
        "quote_payload": quote_payload,
        "verifier_result": verifier_result,
        "quran_span": quran_span,
        "error": None,
    }
