from __future__ import annotations

from pathlib import Path
from typing import Any

from domains.quran.citations.resolver import resolve_quran_reference
from domains.quran.retrieval.fetcher import fetch_quran_span
from domains.quran.retrieval.metadata_loader import DEFAULT_QURAN_ARABIC_PATH, load_quran_metadata
from domains.quran.retrieval.translation_fetcher import DEFAULT_QURAN_TRANSLATION_PATH
from domains.quran.repositories.context import resolve_quran_repository_context


def explain_quran_reference(
    query: str,
    *,
    resolution: dict[str, Any] | None = None,
    quran_metadata: dict[int, dict[str, Any]] | None = None,
    quran_csv_path: str | Path = DEFAULT_QURAN_ARABIC_PATH,
    translation_csv_path: str | Path = DEFAULT_QURAN_TRANSLATION_PATH,
    repository_mode: str | None = None,
    database_url: str | None = None,
    quran_work_source_id: str | None = None,
    translation_work_source_id: str | None = None,
) -> dict[str, Any]:
    """Resolve an explicit Quran reference and return the fetched span."""
    repository_context = resolve_quran_repository_context(
        repository_mode=repository_mode,
        database_url=database_url,
        quran_work_source_id=quran_work_source_id,
        translation_work_source_id=translation_work_source_id,
    )
    metadata = quran_metadata or load_quran_metadata(
        quran_csv_path,
        repository_mode=repository_context.repository_mode,
        database_url=repository_context.database_url,
        work_source_id=repository_context.quran_work_source_id,
    )
    resolution = resolution or resolve_quran_reference(query, quran_metadata=metadata)

    if not resolution.get("resolved"):
        return {
            "ok": False,
            "intent": "explicit_quran_reference_explain",
            "query": query,
            "resolution": resolution,
            "quran_span": None,
            "error": resolution.get("error") or "could_not_resolve_reference",
        }

    quran_span = fetch_quran_span(
        surah_no=int(resolution["surah_no"]),
        ayah_start=int(resolution["ayah_start"]),
        ayah_end=int(resolution["ayah_end"]),
        metadata=metadata,
        quran_csv_path=quran_csv_path,
        translation_csv_path=translation_csv_path,
        repository_mode=repository_context.repository_mode,
        database_url=repository_context.database_url,
        quran_work_source_id=repository_context.quran_work_source_id,
        translation_work_source_id=repository_context.translation_work_source_id,
    )

    return {
        "ok": True,
        "intent": "explicit_quran_reference_explain",
        "query": query,
        "resolution": resolution,
        "quran_span": quran_span,
        "error": None,
    }
