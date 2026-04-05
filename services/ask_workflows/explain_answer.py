from __future__ import annotations

from fastapi import Request

from domains.ask.workflows.explain_answer import explain_answer as _domain_explain_answer


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
    debug: bool = False,
) -> dict[str, object]:
    return _domain_explain_answer(
        query=query,
        request=request,
        route=route,
        include_tafsir=include_tafsir,
        tafsir_source_id=tafsir_source_id,
        tafsir_limit=tafsir_limit,
        database_url=database_url,
        repository_mode=repository_mode,
        quran_work_source_id=quran_work_source_id,
        translation_work_source_id=translation_work_source_id,
        debug=debug,
    )
