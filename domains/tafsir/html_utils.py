from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from lxml import html

_TAG_BREAK_RE = re.compile(r"<(?:/p|/div|/h[1-6]|br\s*/?)>", re.IGNORECASE)


def strip_html_to_text(value: str) -> str:
    raw = value or ""
    if not raw.strip():
        return ""

    try:
        fragments = html.fragments_fromstring(raw)
    except (html.ParserError, ValueError):
        softened = _TAG_BREAK_RE.sub("\n", raw)
        softened = re.sub(r"<[^>]+>", " ", softened)
        return _normalize_preserving_paragraphs(softened)

    parts: list[str] = []
    for fragment in fragments:
        if isinstance(fragment, str):
            text = fragment
        else:
            text = fragment.text_content()
        cleaned = _normalize_preserving_paragraphs(text)
        if cleaned:
            parts.append(cleaned)
    return "\n\n".join(parts).strip()


def normalize_search_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "")).strip()


def compute_text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_preserving_paragraphs(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
