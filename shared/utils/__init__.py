"""Shared utility exports for future-state runtime ownership."""

from shared.utils.arabic_text import (
    collapse_whitespace,
    normalize_arabic_aggressive,
    normalize_arabic_light,
    sanitize_quran_text_for_matching,
    sanitize_quran_text_for_matching_with_meta,
    tokenize,
)

__all__ = [
    "collapse_whitespace",
    "normalize_arabic_aggressive",
    "normalize_arabic_light",
    "sanitize_quran_text_for_matching",
    "sanitize_quran_text_for_matching_with_meta",
    "tokenize",
]
