from __future__ import annotations

import re
from typing import Any

from domains.ask.planner_types import AbstentionReason

HADITH_HINT_RE = re.compile(
    r"\b(?:hadith|ahadith|bukhari|muslim|tirmidhi|ab[ui] dawud|nasai|ibn majah)\b",
    re.IGNORECASE,
)

TOPICAL_HINT_RE = re.compile(
    r"\b(?:what does islam say|islam says|riba|anxiety|patience|marriage|inheritance|zakat|dua|shirk|halal|haram)\b",
    re.IGNORECASE,
)

CLARIFICATION_HINT_RE = re.compile(
    r"\b(?:this|that|it|the verse|the quote)\b",
    re.IGNORECASE,
)


def infer_unsupported_abstention_reason(query: str, route: dict[str, Any] | None = None) -> AbstentionReason:
    text = " ".join((query or "").lower().split())
    route = route or {}

    if HADITH_HINT_RE.search(text):
        return AbstentionReason.HADITH_NOT_SUPPORTED_YET
    if not text:
        return AbstentionReason.NEEDS_CLARIFICATION
    if route.get("reason") == "empty_query":
        return AbstentionReason.NEEDS_CLARIFICATION
    if CLARIFICATION_HINT_RE.fullmatch(text):
        return AbstentionReason.NEEDS_CLARIFICATION
    if TOPICAL_HINT_RE.search(text):
        return AbstentionReason.UNSUPPORTED_CAPABILITY
    return AbstentionReason.UNSUPPORTED_DOMAIN


def reason_to_error_code(reason: AbstentionReason | str | None) -> str | None:
    if reason is None:
        return None
    if isinstance(reason, AbstentionReason):
        return reason.value
    return str(reason)
