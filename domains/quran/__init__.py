from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "resolve_quran_reference": ("domains.quran.citations.resolver", "resolve_quran_reference"),
    "load_quran_metadata": ("domains.quran.repositories.metadata_repository", "load_quran_metadata"),
    "fetch_quran_span": ("domains.quran.retrieval.fetcher", "fetch_quran_span"),
    "build_health_payload": ("domains.quran.verifier.service", "build_health_payload"),
    "verify_quran_text": ("domains.quran.verifier.service", "verify_quran_text"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    return getattr(import_module(module_name), attr_name)
