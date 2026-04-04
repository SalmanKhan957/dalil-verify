from __future__ import annotations

from pathlib import Path
from typing import Any

from services.citation_resolver.resolver import resolve_quran_reference
from services.quran_retrieval.fetcher import fetch_quran_span
from services.quran_retrieval.metadata_loader import DEFAULT_QURAN_ARABIC_PATH, load_quran_metadata
from services.quran_retrieval.translation_fetcher import DEFAULT_QURAN_TRANSLATION_PATH


def explain_quran_reference(
    query: str,
    *,
    resolution: dict[str, Any] | None = None,
    quran_metadata: dict[int, dict[str, Any]] | None = None,
    quran_csv_path: str | Path = DEFAULT_QURAN_ARABIC_PATH,
    translation_csv_path: str | Path = DEFAULT_QURAN_TRANSLATION_PATH,
) -> dict[str, Any]:
    """Resolve an explicit Quran reference and return the fetched span.

    This is the first Ask lane. It stays deliberately narrow: explicit citation
    in, structured Quran span out.
    """
    metadata = quran_metadata or load_quran_metadata(quran_csv_path)
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
    )

    return {
        "ok": True,
        "intent": "explicit_quran_reference_explain",
        "query": query,
        "resolution": resolution,
        "quran_span": quran_span,
        "error": None,
    }
