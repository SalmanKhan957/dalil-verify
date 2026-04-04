from __future__ import annotations

"""Compatibility shim around the shared Quran runtime bootstrap.

The application runtime now lives under services.quran_runtime.* so app modules do
not import core verifier machinery from scripts/* directly.
"""

from services.quran_runtime import bootstrap as _bootstrap
from services.quran_runtime.bootstrap import lifespan
from services.quran_runtime.types import CorpusRuntime


def __getattr__(name: str):
    if name in {
        "QURAN_DATA_PATH",
        "QURAN_PASSAGE_DATA_PATH",
        "QURAN_UTHMANI_DATA_PATH",
        "QURAN_UTHMANI_PASSAGE_DATA_PATH",
        "QURAN_EN_TRANSLATION_PATH",
        "QURAN_PASSAGE_NEIGHBOR_INDEX_PATH",
        "SIMPLE_RUNTIME",
        "UTHMANI_RUNTIME",
        "ENGLISH_TRANSLATION_MAP",
        "ENGLISH_TRANSLATION_INFO",
        "PASSAGE_NEIGHBOR_LOOKUP",
        "refresh_runtime_state",
        "ensure_runtime_state_loaded",
        "runtime_state_loaded",
        "RUNTIME_BOOT_INFO",
    }:
        return getattr(_bootstrap, name)
    raise AttributeError(name)
