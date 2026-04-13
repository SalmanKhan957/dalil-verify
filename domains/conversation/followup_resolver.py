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
    rejected: bool = False


_SIMPLIFY_PATTERNS = [
    re.compile(
        r"\b(?:simplify(?:\s+(?:this|that|it))?|simpler|more\s+simply|easy\s+words|plain\s+words|simple\s+words|say\s+(?:it|that)\s+more\s+simply|explain\s+(?:it|this|that)\s+in\s+(?:simple|plain)\s+words|explain\s+(?:it|this|that)\s+simply)\b",
        re.I,
    )
]
_SUMMARIZE_PATTERNS = [re.compile(r"\b(summarize|summary|sum up)\b", re.I)]
_LESSON_PATTERNS = [re.compile(r"\b(lesson|teaches|teaching|takeaway)\b", re.I)]
_REPEAT_PATTERNS = [re.compile(r"\b(exact wording|show.*again|repeat.*again|quote.*again)\b", re.I)]
_ORDINAL_VERSE_RE = re.compile(r"\b(?P<ordinal>first|1st|second|2nd|third|3rd|fourth|4th|last)\s+verse\b", re.I)
_NEXT_VERSE_RE = re.compile(r"\b(?:next|after)\s+verse\b|\bgo\s+to\s+the\s+next\s+verse\b", re.I)
_PREVIOUS_VERSE_RE = re.compile(r"\b(?:previous|prev|before)\s+verse\b|\bgo\s+to\s+the\s+previous\s+verse\b", re.I)
_HADITH_TOPIC_SHIFT_RE = re.compile(r"\b(?:ahadith|hadiths|hadith\s+about|give me hadith|give me ahadith)\b", re.I)
_BROAD_TOPIC_SHIFT_RE = re.compile(r"\b(?:what does islam say about|generally|in general|theme|topical tafsir|about this theme)\b", re.I)


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


def _capability_for_phrase_param(state: SessionState, action_type: FollowupAction, key: str, value: str) -> FollowupCapability | None:
    for item in derive_followup_capabilities(state).sorted():
        if item.action_type != action_type:
            continue
        if str(item.phrase_params.get(key) or '').strip().lower() == value:
            return item
    return None


def _out_of_scope_source_request(query: str, state: SessionState) -> ResolvedFollowup | None:
    for source_id, pattern in _SOURCE_LABEL_PATTERNS.items():
        if not pattern.search(query):
            continue
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
        if state.has_quran_scope() and source_id in list(state.scope.effective_tafsir_source_ids()):
            return ResolvedFollowup(
                matched=True,
                action_type=FollowupAction.FOCUS_SOURCE,
                target_domain='tafsir',
                target_source_id=source_id,
                target_ref=state.scope.quran_ref,
                confidence=0.94,
                reason='thread_scope_source_specific_followup',
            )
        return ResolvedFollowup(matched=False, rejected=True, reason='followup_target_source_not_in_scope')
    return None


def _looks_like_new_query_boundary(query: str, state: SessionState) -> bool:
    normalized = query.strip()
    if not normalized or not state.has_quran_scope():
        return False
    if _HADITH_TOPIC_SHIFT_RE.search(normalized):
        return True
    if _BROAD_TOPIC_SHIFT_RE.search(normalized):
        return True
    return False


def resolve_followup(query: str, state: SessionState) -> ResolvedFollowup:
    normalized = query.strip()
    if not normalized or not state.supports_followups():
        return ResolvedFollowup(matched=False)

    source_result = _out_of_scope_source_request(normalized, state)
    if source_result is not None:
        return source_result

    if _looks_like_new_query_boundary(normalized, state):
        return ResolvedFollowup(matched=False, rejected=True, reason='followup_requires_new_query_boundary')

    ordinal_match = _ORDINAL_VERSE_RE.search(normalized)
    if ordinal_match:
        ordinal = str(ordinal_match.group('ordinal') or '').strip().lower()
        cap = _capability_for_phrase_param(state, FollowupAction.SELECT_QURAN_VERSE, 'ordinal', ordinal)
        if cap:
            return ResolvedFollowup(True, cap.action_type, cap.target_domain, cap.target_source_id, cap.target_ref, 0.94, 'quran_ordinal_followup')
        return ResolvedFollowup(matched=False, rejected=True, reason='followup_span_not_available')

    if _NEXT_VERSE_RE.search(normalized):
        cap = _first_capability(state, FollowupAction.NAVIGATE_NEXT_VERSE)
        if cap:
            return ResolvedFollowup(True, cap.action_type, cap.target_domain, cap.target_source_id, cap.target_ref, 0.95, 'quran_next_verse_followup')
        return ResolvedFollowup(matched=False, rejected=True, reason='followup_span_not_available')

    if _PREVIOUS_VERSE_RE.search(normalized):
        cap = _first_capability(state, FollowupAction.NAVIGATE_PREVIOUS_VERSE)
        if cap:
            return ResolvedFollowup(True, cap.action_type, cap.target_domain, cap.target_source_id, cap.target_ref, 0.95, 'quran_previous_verse_followup')
        return ResolvedFollowup(matched=False, rejected=True, reason='followup_span_not_available')

    if any(p.search(normalized) for p in _SIMPLIFY_PATTERNS):
        cap = _first_capability(state, FollowupAction.SIMPLIFY)
        if cap:
            return ResolvedFollowup(True, cap.action_type, cap.target_domain, cap.target_source_id, cap.target_ref, 0.90, 'simplify_followup')
        return ResolvedFollowup(matched=False, rejected=True, reason='followup_action_not_supported_for_scope')

    if any(p.search(normalized) for p in _SUMMARIZE_PATTERNS):
        cap = _first_capability(state, FollowupAction.SUMMARIZE_HADITH)
        if cap:
            return ResolvedFollowup(True, cap.action_type, cap.target_domain, cap.target_source_id, cap.target_ref, 0.95, 'hadith_summary_followup')
        if state.has_quran_scope():
            return ResolvedFollowup(matched=False, rejected=True, reason='followup_action_not_supported_for_scope')

    if any(p.search(normalized) for p in _LESSON_PATTERNS):
        cap = _first_capability(state, FollowupAction.EXTRACT_HADITH_LESSON)
        if cap:
            return ResolvedFollowup(True, cap.action_type, cap.target_domain, cap.target_source_id, cap.target_ref, 0.94, 'hadith_lesson_followup')
        if state.has_quran_scope():
            return ResolvedFollowup(matched=False, rejected=True, reason='followup_action_not_supported_for_scope')

    if any(p.search(normalized) for p in _REPEAT_PATTERNS):
        cap = _first_capability(state, FollowupAction.REPEAT_EXACT_TEXT)
        if cap:
            return ResolvedFollowup(True, cap.action_type, cap.target_domain, cap.target_source_id, cap.target_ref, 0.88, 'repeat_exact_text_followup')
        return ResolvedFollowup(matched=False, rejected=True, reason='followup_missing_anchor')

    return ResolvedFollowup(matched=False)
