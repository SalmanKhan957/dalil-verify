"""Compatibility package for Quran.Foundation client wrappers."""

from infrastructure.clients.quran_foundation import (
    ApiPagination,
    QuranFoundationContentClient,
    QuranFoundationResourcesAPI,
    QuranFoundationSettings,
    QuranFoundationTafsirAPI,
    QuranFoundationTokenProvider,
    TafsirAyahEntry,
    TafsirChapterNotFoundError,
    TafsirResource,
)

__all__ = [
    "ApiPagination",
    "QuranFoundationContentClient",
    "QuranFoundationResourcesAPI",
    "QuranFoundationSettings",
    "QuranFoundationTafsirAPI",
    "QuranFoundationTokenProvider",
    "TafsirAyahEntry",
    "TafsirChapterNotFoundError",
    "TafsirResource",
]
