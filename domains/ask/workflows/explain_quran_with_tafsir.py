from __future__ import annotations

from pathlib import Path
from typing import Any

from domains.ask.workflows.explain_quran_reference import explain_quran_reference
from domains.ask.workflows.tafsir_attachment import attach_tafsir_to_quran_result
from domains.quran.retrieval.metadata_loader import DEFAULT_QURAN_ARABIC_PATH
from domains.quran.retrieval.translation_fetcher import DEFAULT_QURAN_TRANSLATION_PATH
from domains.quran.repositories.context import resolve_quran_repository_context
from domains.tafsir.formatter import build_tafsir_citation
from domains.tafsir.service import TafsirService


def explain_quran_with_tafsir(
    *,
    query: str,
    resolution: dict[str, Any] | None = None,
    include_tafsir: bool = False,
    tafsir_source_id: str = "tafsir:ibn-kathir-en",
    tafsir_limit: int = 3,
    database_url: str | None = None,
    quran_csv_path: str | Path = DEFAULT_QURAN_ARABIC_PATH,
    translation_csv_path: str | Path = DEFAULT_QURAN_TRANSLATION_PATH,
    repository_mode: str | None = None,
    quran_work_source_id: str = DEFAULT_QURAN_TEXT_WORK_SOURCE_ID,
    translation_work_source_id: str = DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID,
) -> dict[str, Any]:
    repository_context = resolve_quran_repository_context(
        repository_mode=repository_mode,
        database_url=database_url,
        quran_work_source_id=quran_work_source_id,
        translation_work_source_id=translation_work_source_id,
    )
    base_result = explain_quran_reference(
        query,
        resolution=resolution,
        quran_csv_path=quran_csv_path,
        translation_csv_path=translation_csv_path,
        repository_mode=repository_context.repository_mode,
        database_url=repository_context.database_url,
        quran_work_source_id=repository_context.quran_work_source_id,
        translation_work_source_id=repository_context.translation_work_source_id,
    )
    return attach_tafsir_to_quran_result(
        base_result,
        include_tafsir=include_tafsir,
        tafsir_source_id=tafsir_source_id,
        tafsir_limit=tafsir_limit,
        database_url=repository_context.database_url,
        tafsir_service_factory=TafsirService,
        citation_builder=build_tafsir_citation,
    )
