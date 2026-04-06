from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ['compose_explain_answer']


def __getattr__(name: str) -> Any:
    if name != 'compose_explain_answer':  # pragma: no cover
        raise AttributeError(name)
    return getattr(import_module('services.answer_engine.composer'), name)
