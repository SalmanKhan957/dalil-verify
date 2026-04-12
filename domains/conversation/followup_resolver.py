from __future__ import annotations

import re
from dataclasses import dataclass

from .followup_capabilities import FollowupAction, FollowupCapability, derive_followup_capabilities
from .session_state import SessionState


@dataclass(slots=True)
class ResolvedFollowup:
    matched: bool
    action_type: str | None = None
    target_domain: str | None = None
    target_source_id: str | None = None
    target_ref: str | None = None
    confidence: float = 0.0
    reason: str | None = None


_SIMPLIFY_PATTERNS = [
    re.compile(r"\b(simplify|simpler|more simply|easy words|plain words)\b", re.I),
]
_SUMMARIZE_PATTERNS = [
    re.compile(r"\b(summarize|summary|sum up)\b", re.I),
]
_LESSON_PATTERNS = [
    re.compile(r"\b(lesson|teaches|teaching|takeaway)\b", re.I),
]
_REPEAT_PATTERNS = [
    re.compile(r"\b(exact wording|show.*again|repeat.*again|quote.*again)\b", re.I),
]
_SECOND_VERSE_PATTERNS = [
    re.compile(r"\b(second verse|2nd verse|next verse)\b", re.I),
]


_SOURCE_LABEL_PATTERNS = {
    "tafsir:tafheem-al-quran-en": re.compile(r"\btafheem\b", re.I),
    "tafsir:ibn-kathir-en": re.compile(r"\b(ibn kathir|kathir)\b", re.I),
    "tafsir:maarif-al-quran-en": re.compile(r"\b(maarif|ma'arif)\b", re.I),
}


def _first_capability(state: SessionState, action_type: FollowupAction) -> FollowupCapability | None:
    caps = derive_followup_capabilities(state).sorted()
    for item in caps:
        if item.action_type == action_type:
            return item
    return None


def resolve_followup(query: str, state: SessionState) -> ResolvedFollowup:
    normalized = query.strip()
    if not normalized or not state.supports_followups():
        return ResolvedFollowup(matched=False)

    for source_id, pattern in _SOURCE_LABEL_PATTERNS.items():
        if pattern.search(normalized):
            for capability in derive_followup_capabilities(state).sorted():
                if capability.action_type == FollowupAction.FOCUS_SOURCE and capability.target_source_id == source_id:
                    return ResolvedFollowup(
                        matched=True,
                        action_type=capability.action_type,
                        target_domain=capability.target_domain,
                        target_source_id=capability.target_source_id,
                        target_ref=capability.target_ref,
                        confidence=0.96,
                        reason="source_specific_followup",
                    )

    if any(p.search(normalized) for p in _SECOND_VERSE_PATTERNS):
        cap = _first_capability(state, FollowupAction.FOCUS_SECOND_VERSE)
        if cap:
            return ResolvedFollowup(True, cap.action_type, cap.target_domain, cap.target_source_id, cap.target_ref, 0.93, "quran_second_verse_followup")

    if any(p.search(normalized) for p in _SIMPLIFY_PATTERNS):
        cap = _first_capability(state, FollowupAction.SIMPLIFY)
        if cap:
            return ResolvedFollowup(True, cap.action_type, cap.target_domain, cap.target_source_id, cap.target_ref, 0.9, "simplify_followup")

    if any(p.search(normalized) for p in _SUMMARIZE_PATTERNS):
        cap = _first_capability(state, FollowupAction.SUMMARIZE_HADITH)
        if cap:
            return ResolvedFollowup(True, cap.action_type, cap.target_domain, cap.target_source_id, cap.target_ref, 0.95, "hadith_summary_followup")

    if any(p.search(normalized) for p in _LESSON_PATTERNS):
        cap = _first_capability(state, FollowupAction.EXTRACT_HADITH_LESSON)
        if cap:
            return ResolvedFollowup(True, cap.action_type, cap.target_domain, cap.target_source_id, cap.target_ref, 0.94, "hadith_lesson_followup")

    if any(p.search(normalized) for p in _REPEAT_PATTERNS):
        cap = _first_capability(state, FollowupAction.REPEAT_EXACT_TEXT)
        if cap:
            return ResolvedFollowup(True, cap.action_type, cap.target_domain, cap.target_source_id, cap.target_ref, 0.88, "repeat_exact_text_followup")

    return ResolvedFollowup(matched=False)
