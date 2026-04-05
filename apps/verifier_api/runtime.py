from __future__ import annotations

"""Compatibility shim around the shared Quran runtime bootstrap.

The verifier runtime now lives under ``domains.quran.verifier`` and app modules
should not import core verifier machinery from legacy script-era helpers.
"""

from domains.quran.verifier import bootstrap as _bootstrap
from domains.quran.verifier.bootstrap import lifespan
from domains.quran.verifier.types import CorpusRuntime


__all__ = ["lifespan", "CorpusRuntime"]


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
        "SOURCE_GOVERNANCE_INFO",
    }:
        return getattr(_bootstrap, name)
    raise AttributeError(name)
