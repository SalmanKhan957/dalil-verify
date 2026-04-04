# services/citation_resolver/normalizer.py

from __future__ import annotations

import re

DASH_RE = re.compile(r"[–—−]")
MULTISPACE_RE = re.compile(r"\s+")
SURAH_AYAH_SEPARATOR_RE = re.compile(r"\s*:\s*")
RANGE_SEPARATOR_RE = re.compile(r"\s*-\s*")
TRAILING_PUNCT_RE = re.compile(r"[?!.:,;]+$")

# Keep this conservative. This is a resolver, not an NLP cleaner.
LEADING_FILLER_PATTERNS = [
    re.compile(r"^\s*explain\s+", re.IGNORECASE),
    re.compile(r"^\s*tafsir\s+of\s+", re.IGNORECASE),
    re.compile(r"^\s*meaning\s+of\s+", re.IGNORECASE),
    re.compile(r"^\s*what\s+does\s+", re.IGNORECASE),
    re.compile(r"^\s*what\s+is\s+the\s+meaning\s+of\s+", re.IGNORECASE),
    re.compile(r"^\s*what\s+is\s+the\s+tafsir\s+of\s+", re.IGNORECASE),
]

TRAILING_FILLER_PATTERNS = [
    re.compile(r"\s+mean\??\s*$", re.IGNORECASE),
    re.compile(r"\s+means\??\s*$", re.IGNORECASE),
    re.compile(r"\s+meaning\??\s*$", re.IGNORECASE),
    re.compile(r"\s+tafsir\??\s*$", re.IGNORECASE),
]


def _strip_safe_filler(text: str) -> str:
    value = text.strip()

    for pattern in LEADING_FILLER_PATTERNS:
        value = pattern.sub("", value).strip()

    for pattern in TRAILING_FILLER_PATTERNS:
        value = pattern.sub("", value).strip()

    return value


def normalize_reference_text(text: str) -> str:
    """
    Normalize user input into a parser-friendly reference string.

    Examples:
    - "Explain 94:5" -> "94:5"
    - "Explain 94:5–6" -> "94:5-6"
    - "Tafsir of Surah Ikhlas" -> "surah ikhlas"
    - "What does Surah Ash-Sharh 5 mean?" -> "surah ash-sharh 5"
    """
    value = (text or "").strip()
    if not value:
        return ""

    value = DASH_RE.sub("-", value)
    value = value.lower()
    value = MULTISPACE_RE.sub(" ", value).strip()
    value = TRAILING_PUNCT_RE.sub("", value).strip()

    value = _strip_safe_filler(value)

    # Normalize colon spacing, e.g. "94 : 5" -> "94:5"
    value = SURAH_AYAH_SEPARATOR_RE.sub(":", value)

    # Normalize hyphen spacing, e.g. "5 - 6" -> "5-6"
    value = RANGE_SEPARATOR_RE.sub("-", value)

    # Final whitespace cleanup
    value = MULTISPACE_RE.sub(" ", value).strip()

    return value