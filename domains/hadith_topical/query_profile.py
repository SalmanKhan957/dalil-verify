from __future__ import annotations

from domains.query_intelligence.query_family_classifier import classify_query_family

_FAMILY_TO_PROFILE = {
    'hadith_prophetic_guidance': 'prophetic_guidance',
    'hadith_topic_request': 'guidance',
    'hadith_broad_virtue': 'guidance',
}

_WARNING_MARKERS = ('warning', 'punishment', 'danger', 'consequence', 'avoid', 'stay away from')
_VIRTUE_MARKERS = ('virtue', 'benefit', 'merit', 'best of', 'reward of', 'excellence of')


def infer_query_profile(query: str) -> str:
    lowered = (query or '').casefold().strip()
    if any(marker in lowered for marker in _WARNING_MARKERS):
        return 'warning'
    if any(marker in lowered for marker in _VIRTUE_MARKERS):
        return 'virtue'
    family = classify_query_family(query)
    if family is not None:
        return _FAMILY_TO_PROFILE.get(family.family_id, family.query_profile or 'general_topic')
    return 'general_topic'
