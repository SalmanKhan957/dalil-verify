from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    'ApiPagination': ('infrastructure.clients.quran_foundation.models', 'ApiPagination'),
    'QuranFoundationContentClient': ('infrastructure.clients.quran_foundation.client', 'QuranFoundationContentClient'),
    'QuranFoundationResourcesAPI': ('infrastructure.clients.quran_foundation.resources_api', 'QuranFoundationResourcesAPI'),
    'QuranFoundationSettings': ('infrastructure.clients.quran_foundation.config', 'QuranFoundationSettings'),
    'QuranFoundationTafsirAPI': ('infrastructure.clients.quran_foundation.tafsir_api', 'QuranFoundationTafsirAPI'),
    'QuranFoundationTokenProvider': ('infrastructure.clients.quran_foundation.auth', 'QuranFoundationTokenProvider'),
    'TafsirAyahEntry': ('infrastructure.clients.quran_foundation.models', 'TafsirAyahEntry'),
    'TafsirChapterNotFoundError': ('infrastructure.clients.quran_foundation.tafsir_api', 'TafsirChapterNotFoundError'),
    'TafsirResource': ('infrastructure.clients.quran_foundation.models', 'TafsirResource'),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:  # pragma: no cover
        raise AttributeError(name) from exc
    return getattr(import_module(module_name), attr_name)
