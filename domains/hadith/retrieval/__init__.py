from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ['HadithCitationLookupService']


def __getattr__(name: str) -> Any:
    if name == 'HadithCitationLookupService':
        return import_module('domains.hadith.retrieval.citation_lookup').HadithCitationLookupService
    raise AttributeError(name)
