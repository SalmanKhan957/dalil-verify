from __future__ import annotations

from typing import Any

ANSWER_SURFACE_FIELDS: tuple[str, ...] = (
    "answer_mode",
    "answer_text",
    "citations",
    "quran_support",
    "tafsir_support",
    "resolution",
    "partial_success",
    "warnings",
    "quran_source_selection",
    "debug",
)


def extract_answer_surface(result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}

    payload: dict[str, Any] = {}
    for field in ANSWER_SURFACE_FIELDS:
        if field in result:
            payload[field] = result.get(field)

    return payload


def build_ask_response_payload(
    *,
    query: str,
    route: dict[str, Any],
    result: dict[str, Any] | None,
) -> dict[str, Any]:
    result_dict = result or {}

    payload: dict[str, Any] = {
        "ok": bool(result_dict.get("ok")),
        "query": query,
        "route_type": str(route.get("route_type") or result_dict.get("route_type") or "unsupported_for_now"),
        "action_type": str(route.get("action_type") or result_dict.get("action_type") or "unknown"),
        "route": route,
        "result": result,
        "error": result_dict.get("error"),
    }
    payload.update(extract_answer_surface(result_dict))
    return payload
