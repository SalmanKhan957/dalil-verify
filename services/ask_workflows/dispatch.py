from __future__ import annotations

from fastapi import Request

from services.ask_router.classifier import classify_ask_query
from services.ask_router.route_types import AskActionType, AskRouteType
from services.ask_workflows.explain_answer import explain_answer
from services.ask_workflows.verifier_support import run_arabic_quran_quote_workflow


def dispatch_ask_query(query: str, *, request: Request | None = None, debug: bool = False) -> dict[str, object]:
    route = classify_ask_query(query)
    route_type = route["route_type"]
    action_type = route.get("action_type", AskActionType.UNKNOWN.value)

    if route_type == AskRouteType.EXPLICIT_QURAN_REFERENCE.value:
        result = explain_answer(query=query, request=request, debug=debug)
        quran_support = result.get("quran_support") or {}
        if quran_support and "quran_span" not in result:
            result["quran_span"] = {
                "citation_string": quran_support.get("citation_string"),
                "canonical_source_id": quran_support.get("canonical_source_id"),
                "surah_no": quran_support.get("surah_no"),
                "ayah_start": quran_support.get("ayah_start"),
                "ayah_end": quran_support.get("ayah_end"),
                "surah_name_en": quran_support.get("surah_name_en"),
                "surah_name_ar": quran_support.get("surah_name_ar"),
                "arabic_text": quran_support.get("arabic_text"),
                "translation": {
                    "text": quran_support.get("translation_text"),
                    "source_id": quran_support.get("translation_source_id"),
                },
                "ayah_rows": [],
            }
        return {
            "ok": bool(result.get("ok")),
            "query": query,
            "route_type": route_type,
            "action_type": action_type,
            "route": route,
            "result": result,
            "error": result.get("error"),
        }

    if route_type == AskRouteType.ARABIC_QURAN_QUOTE.value:
        quote_payload = route.get("quote_payload") or query
        result = run_arabic_quran_quote_workflow(
            query,
            quote_payload=quote_payload,
            action_type=action_type,
            request=request,
            debug=debug,
        )
        return {
            "ok": bool(result.get("ok")),
            "query": query,
            "route_type": route_type,
            "action_type": action_type,
            "route": route,
            "result": result,
            "error": result.get("error"),
        }

    return {
        "ok": False,
        "query": query,
        "route_type": AskRouteType.UNSUPPORTED_FOR_NOW.value,
        "action_type": AskActionType.UNKNOWN.value,
        "route": route,
        "result": None,
        "error": "unsupported_query_type_for_now",
    }
