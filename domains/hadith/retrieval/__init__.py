from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ['HadithCitationLookupService', 'HadithLexicalSearchService']


def __getattr__(name: str) -> Any:
    if name == 'HadithCitationLookupService':
        return import_module('domains.hadith.retrieval.citation_lookup').HadithCitationLookupService
    if name == 'HadithLexicalSearchService':
        return import_module('domains.hadith.retrieval.lexical_search').HadithLexicalSearchService
    raise AttributeError(name)
