from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ['TafsirLexicalSearchService']


def __getattr__(name: str) -> Any:
    if name == 'TafsirLexicalSearchService':
        return import_module('domains.tafsir.retrieval.lexical_search').TafsirLexicalSearchService
    raise AttributeError(name)
