from __future__ import annotations

import re

ARABIC_DIACRITICS_RE = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]"
)
WHITESPACE_RE = re.compile(r"\s+")
TATWEEL = "\u0640"

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
})


def collapse_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def normalize_arabic_light(text: str) -> str:
    """
    Conservative normalization for primary matching.
    Good balance between recall and precision.
    """
    if not text:
        return ""

    text = text.strip()
    text = text.replace(TATWEEL, "")

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