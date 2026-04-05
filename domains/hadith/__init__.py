from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    'HadithService',
    'parse_hadith_citation',
    'render_hadith_citation',
    'HadithCollectionIngestionService',
    'build_default_bukhari_ingestion_service',
]


def __getattr__(name: str) -> Any:
    if name == 'HadithService':
        return import_module('domains.hadith.service').HadithService
    if name == 'parse_hadith_citation':
        return import_module('domains.hadith.citations.parser').parse_hadith_citation
    if name == 'render_hadith_citation':
        return import_module('domains.hadith.citations.renderer').render_hadith_citation
    if name in {'HadithCollectionIngestionService', 'build_default_bukhari_ingestion_service'}:
        mod = import_module('domains.hadith.ingestion.ingest_collection')
        return getattr(mod, name)
    raise AttributeError(name)
