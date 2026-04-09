from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    'TafsirRepository',
    'SqlAlchemyTafsirRepository',
    'TafsirLexicalSearchRepository',
    'SqlAlchemyTafsirLexicalSearchRepository',
]


def __getattr__(name: str) -> Any:
    if name in {'TafsirRepository', 'SqlAlchemyTafsirRepository'}:
        mod = import_module('domains.tafsir.repositories.tafsir_repository')
        return getattr(mod, name)
    if name in {'TafsirLexicalSearchRepository', 'SqlAlchemyTafsirLexicalSearchRepository'}:
        mod = import_module('domains.tafsir.repositories.lexical_search_repository')
        return getattr(mod, name)
    raise AttributeError(name)
