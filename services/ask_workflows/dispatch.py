from __future__ import annotations

from fastapi import Request

from services.ask_router.classifier import classify_ask_query
from services.ask_workflows.explain_answer import explain_answer


def dispatch_ask_query(query: str, *, request: Request | None = None, debug: bool = False) -> dict[str, object]:
    route = classify_ask_query(query)
    result = explain_answer(
        query=query,
        request=request,
        route=route,
        include_tafsir=None,
        debug=debug,
    )
    return {
        "ok": bool(result.get("ok")),
        "query": query,
        "route_type": str(route.get("route_type") or result.get("route_type") or "unsupported_for_now"),
        "action_type": str(route.get("action_type") or result.get("action_type") or "unknown"),
        "route": route,
        "result": result,
        "error": result.get("error"),
    }
