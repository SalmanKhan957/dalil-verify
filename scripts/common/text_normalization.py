from __future__ import annotations

import re

ARABIC_DIACRITICS_RE = re.compile(
    r"[ؐ-ًؚ-ٰٟۖ-ۭ]"
)
WHITESPACE_RE = re.compile(r"\s+")
TATWEEL = "ـ"

# Invisible formatting and bidi control characters that often appear in pasted mushaf text.
FORMAT_CONTROL_RE = re.compile(r"[​-‏‪-‮⁦-⁩﻿]")

# Verse ornaments and standalone verse numbers copied from web/app mushaf renderers.
VERSE_ORNAMENTS_RE = re.compile(r"[﴾﴿]")  # ﴾﴿ style marks
STANDALONE_VERSE_NUMBER_RE = re.compile(
    r"(?:(?<=\s)|^)[\(\[\{﴾﴿]*[0-9٠-٩۰-۹]+[\)\]\}﴾﴿]*(?=\s|$)"
)

# Explicit punctuation and Quranic stop marks to strip in aggressive normalization
ARABIC_PUNCT_TRANSLATION = str.maketrans({
    "،": " ",
    "؛": " ",
    "؟": " ",
    "۔": " ",
    ",": " ",
    ";": " ",
    "?": " ",
    "!": " ",
    ":": " ",
    ".": " ",
    "…": " ",
    "ۚ": " ",
    "ۖ": " ",
    "ۗ": " ",
    "ۘ": " ",
    "ۙ": " ",
    "ۛ": " ",
    "ۜ": " ",
    "۝": " ",
    "۞": " ",
    "۩": " ",
    "﴿": " ",
    "﴾": " ",
})


def collapse_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def sanitize_quran_text_for_matching(text: str) -> str:
    """
    Strip copy/paste artifacts that should not affect Quran matching.

    This is intentionally matcher-side sanitation, not user-facing display cleanup.
    """
    if not text:
        return ""

    text = text.strip()
    text = FORMAT_CONTROL_RE.sub("", text)
    text = text.replace(TATWEEL, "")
    text = VERSE_ORNAMENTS_RE.sub(" ", text)
    text = STANDALONE_VERSE_NUMBER_RE.sub(" ", text)
    text = text.translate(ARABIC_PUNCT_TRANSLATION)
    return collapse_whitespace(text)


def normalize_arabic_light(text: str) -> str:
    """
    Conservative normalization for primary matching.
    Good balance between recall and precision.
    """
    if not text:
        return ""

    text = sanitize_quran_text_for_matching(text)

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ؤ": "و",
        "ئ": "ي",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    text = ARABIC_DIACRITICS_RE.sub("", text)
    text = collapse_whitespace(text)
    return text


def normalize_arabic_aggressive(text: str) -> str:
    """
    More aggressive fallback normalization.
    Use for secondary matching signals, not as sole truth layer.
    """
    text = normalize_arabic_light(text)

    aggressive_replacements = {
        "ى": "ا",
        "ة": "ه",
    }
    for src, dst in aggressive_replacements.items():
        text = text.replace(src, dst)

    # Strip Arabic punctuation and Quranic stop marks explicitly
    text = text.translate(ARABIC_PUNCT_TRANSLATION)

    text = collapse_whitespace(text)
    return text


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [t for t in text.split(" ") if t]
