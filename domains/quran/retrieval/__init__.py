from domains.quran.retrieval.fetcher import fetch_quran_span
from domains.quran.retrieval.metadata_loader import DEFAULT_QURAN_ARABIC_PATH, load_quran_metadata
from domains.quran.retrieval.translation_fetcher import DEFAULT_QURAN_TRANSLATION_PATH

__all__ = [
    "DEFAULT_QURAN_ARABIC_PATH",
    "DEFAULT_QURAN_TRANSLATION_PATH",
    "fetch_quran_span",
    "load_quran_metadata",
]
