from __future__ import annotations

from fastapi import Request

from domains.answer_engine.execution import execute_plan
from domains.ask.planner import build_ask_plan
from domains.answer_engine.response_builder import build_explain_answer_payload



def explain_answer(
    *,
    query: str,
    request: Request | None = None,
    route: dict[str, object] | None = None,
    include_tafsir: bool | None = None,
    tafsir_source_id: str | None = "tafsir:ibn-kathir-en",
    tafsir_limit: int = 3,
    database_url: str | None = None,
    debug: bool = False,
) -> dict[str, object]:
    plan = build_ask_plan(
        query,
        route=route,
        request=request,
        include_tafsir=include_tafsir,
        tafsir_source_id=tafsir_source_id,
        tafsir_limit=tafsir_limit,
        database_url=database_url,
        debug=debug,
    )
    evidence = execute_plan(plan, request=request, database_url=database_url)
    return build_explain_answer_payload(plan, evidence)
