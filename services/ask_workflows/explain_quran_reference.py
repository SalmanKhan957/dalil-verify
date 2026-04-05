from __future__ import annotations

from pathlib import Path
from typing import Any

from domains.ask.workflows.explain_quran_reference import explain_quran_reference as _domain_explain_quran_reference
from domains.quran.retrieval.metadata_loader import DEFAULT_QURAN_ARABIC_PATH
from domains.quran.retrieval.translation_fetcher import DEFAULT_QURAN_TRANSLATION_PATH
from domains.quran.repositories.db_repository import (
    DEFAULT_QURAN_TEXT_WORK_SOURCE_ID,
    DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID,
)


def explain_quran_reference(
    query: str,
    *,
    resolution: dict[str, Any] | None = None,
    quran_metadata: dict[int, dict[str, Any]] | None = None,
    quran_csv_path: str | Path = DEFAULT_QURAN_ARABIC_PATH,
    translation_csv_path: str | Path = DEFAULT_QURAN_TRANSLATION_PATH,
    repository_mode: str | None = None,
    database_url: str | None = None,
    quran_work_source_id: str = DEFAULT_QURAN_TEXT_WORK_SOURCE_ID,
    translation_work_source_id: str = DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID,
) -> dict[str, Any]:
    return _domain_explain_quran_reference(
        query,
        resolution=resolution,
        quran_metadata=quran_metadata,
        quran_csv_path=quran_csv_path,
        translation_csv_path=translation_csv_path,
        repository_mode=repository_mode,
        database_url=database_url,
        quran_work_source_id=quran_work_source_id,
        translation_work_source_id=translation_work_source_id,
    )
