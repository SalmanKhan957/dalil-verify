from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    'HadithRepository',
    'SqlAlchemyHadithRepository',
    'HadithLexicalSearchRepository',
    'SqlAlchemyHadithLexicalSearchRepository',
]


def __getattr__(name: str) -> Any:
    if name in {'HadithRepository', 'SqlAlchemyHadithRepository'}:
        mod = import_module('domains.hadith.repositories.hadith_repository')
        return getattr(mod, name)
    if name in {'HadithLexicalSearchRepository', 'SqlAlchemyHadithLexicalSearchRepository'}:
        mod = import_module('domains.hadith.repositories.lexical_search_repository')
        return getattr(mod, name)
    raise AttributeError(name)
