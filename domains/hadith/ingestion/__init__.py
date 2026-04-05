from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ['HadithCollectionIngestionService', 'HadithCollectionNormalizer', 'HadithJsonMirrorNormalizerConfig']


def __getattr__(name: str) -> Any:
    if name == 'HadithCollectionIngestionService':
        return import_module('domains.hadith.ingestion.ingest_collection').HadithCollectionIngestionService
    if name in {'HadithCollectionNormalizer', 'HadithJsonMirrorNormalizerConfig'}:
        mod = import_module('domains.hadith.ingestion.normalizer')
        return getattr(mod, name)
    raise AttributeError(name)
