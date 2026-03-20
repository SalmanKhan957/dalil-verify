from __future__ import annotations

import re

ARABIC_DIACRITICS_RE = re.compile(
    r"[ؐ-ًؚ-ٰٟۖ-ۭ]"
)
QURANIC_ANNOTATION_RE = re.compile(r"[ٰۣ۪ۭٖٜٟ۟۠ۡۢۤۧۨ۫۬ٗ٘ٙٚٛٝٞ]")
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


def sanitize_quran_text_for_matching_with_meta(text: str) -> tuple[str, dict]:
    """
    Strip copy/paste artifacts that should not affect Quran matching.

    This is intentionally matcher-side sanitation, not user-facing display cleanup.
    Returns both the sanitized text and lightweight preprocessing metadata.
    """
    original = text or ""
    if not original:
        return "", {
            "original_char_count": 0,
            "sanitized_char_count": 0,
            "was_sanitized": False,
        }

    working = original.strip()
    working = FORMAT_CONTROL_RE.sub("", working)
    working = working.replace(TATWEEL, "")
    working = VERSE_ORNAMENTS_RE.sub(" ", working)
    working = STANDALONE_VERSE_NUMBER_RE.sub(" ", working)
    working = QURANIC_ANNOTATION_RE.sub("", working)
    working = working.translate(ARABIC_PUNCT_TRANSLATION)
    working = collapse_whitespace(working)

    meta = {
        "original_char_count": len(original),
        "sanitized_char_count": len(working),
        "was_sanitized": working != original.strip(),
    }
    return working, meta


def sanitize_quran_text_for_matching(text: str) -> str:
    sanitized, _ = sanitize_quran_text_for_matching_with_meta(text)
    return sanitized


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
        "ٲ": "ا",
        "ٳ": "ا",
        "ٵ": "ا",
        "ء": "",
        "ؤ": "و",
        "ئ": "ي",
        "ى": "ي",
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


