from __future__ import annotations

from fastapi import Request

from domains.answer_engine.contracts import make_explain_answer_payload
from domains.answer_engine.execution import execute_plan
from domains.answer_engine.response_builder import build_explain_answer_payload
from domains.ask.classifier import classify_ask_query
from domains.ask.planner import build_ask_plan
from domains.quran.repositories.context import (
    resolve_quran_repository_context,
    resolve_requested_quran_repository_source_inputs,
)
from domains.source_registry.db_registry import SourceRegistryDatabaseError


def _build_source_selection_error_payload(
    *,
    query: str,
    route: dict[str, object] | None,
    error: Exception,
    quran_work_source_id: str | None,
    translation_work_source_id: str | None,
    repository_mode: str | None,
    debug: bool,
) -> dict[str, object]:
    resolved_route = route or classify_ask_query(query)
    requested_quran_source_id, requested_translation_source_id = resolve_requested_quran_repository_source_inputs(
        quran_work_source_id=quran_work_source_id,
        translation_work_source_id=translation_work_source_id,
    )
    debug_payload = None
    if debug:
        debug_payload = {
            "repository_error": str(error),
            "requested_quran_work_source_id": requested_quran_source_id,
            "requested_translation_work_source_id": requested_translation_source_id,
            "repository_mode": repository_mode,
        }
    return make_explain_answer_payload(
        ok=False,
        query=query,
        answer_mode="abstain",
        route_type=str(resolved_route.get("route_type") or "unsupported_for_now"),
        action_type=str(resolved_route.get("action_type") or "unknown"),
        answer_text=None,
        citations=[],
        quran_support=None,
        tafsir_support=[],
        resolution=None,
        partial_success=False,
        warnings=["requested_quran_source_override_rejected"],
        debug=debug_payload,
        error=str(error),
        quran_source_selection={
            "repository_mode": repository_mode,
            "source_resolution_strategy": "error",
            "requested_quran_text_source_id": requested_quran_source_id,
            "requested_quran_translation_source_id": requested_translation_source_id,
            "selected_quran_text_source_id": None,
            "selected_quran_translation_source_id": None,
        },
    )


def explain_answer(
    *,
    query: str,
    request: Request | None = None,
    route: dict[str, object] | None = None,
    include_tafsir: bool | None = None,
    tafsir_source_id: str | None = "tafsir:ibn-kathir-en",
    tafsir_limit: int = 3,
    database_url: str | None = None,
    repository_mode: str | None = None,
    quran_work_source_id: str | None = None,
    translation_work_source_id: str | None = None,
    quran_text_source_requested: bool = False,
    quran_translation_source_requested: bool = False,
    debug: bool = False,
) -> dict[str, object]:
    try:
        repository_context = resolve_quran_repository_context(
            repository_mode=repository_mode,
            database_url=database_url,
            quran_work_source_id=quran_work_source_id,
            translation_work_source_id=translation_work_source_id,
        )
        plan = build_ask_plan(
            query,
            route=route,
            request=request,
            include_tafsir=include_tafsir,
            tafsir_source_id=tafsir_source_id,
            tafsir_limit=tafsir_limit,
            database_url=repository_context.database_url,
            repository_mode=repository_context.repository_mode,
            quran_work_source_id=repository_context.quran_work_source_id,
            translation_work_source_id=repository_context.translation_work_source_id,
            quran_text_source_requested=quran_text_source_requested,
            quran_translation_source_requested=quran_translation_source_requested,
            debug=debug,
        )
        evidence = execute_plan(plan, request=request, database_url=repository_context.database_url)
        return build_explain_answer_payload(plan, evidence)
    except (RuntimeError, ValueError, SourceRegistryDatabaseError) as exc:
        return _build_source_selection_error_payload(
            query=query,
            route=route,
            error=exc,
            quran_work_source_id=quran_work_source_id,
            translation_work_source_id=translation_work_source_id,
            repository_mode=repository_mode,
            debug=debug,
        )
