from __future__ import annotations

from typing import Any

from domains.ask.route_types import AskActionType, AskRouteType
from domains.ask.heuristics import detect_tafsir_intent, looks_like_explicit_quran_reference
from domains.hadith_topical.query_topic_resolver import resolve_topic
from domains.query_intelligence.concept_linker import link_query_to_concepts
from domains.query_intelligence.normalization import normalize_topic_query, normalize_user_query
from domains.query_intelligence.query_family_classifier import classify_query_family


class TopicalExposurePolicy:
    INTERNAL = 'internal'
    PUBLIC = 'public'


_MIXED_MULTI_SOURCE_PREFIXES = (
    'what does islam say about',
    "what is islam's view on",
    'what is islam’s view on',
    'islamic view on',
    'what does islam teach about',
)


def _topic_from_family(query: str, family, concept_matches) -> str:
    normalized = normalize_user_query(query)
    lowered = normalized.casefold()
    if family is not None and family.query_profile == 'prophetic_guidance' and concept_matches:
        return concept_matches[0].slug
    matched_cue = ''
    if family is not None:
        matched = tuple(family.matched_cues or ())
        if matched:
            matched_cue = max(matched, key=len)
    if matched_cue and matched_cue in lowered:
        start = lowered.index(matched_cue) + len(matched_cue)
        topic = normalize_topic_query(normalized[start:])
        if topic:
            return topic
    topic = normalize_topic_query(query)
    if topic and topic != normalize_user_query(query):
        return topic
    if concept_matches:
        return concept_matches[0].slug
    return topic or normalize_user_query(query)


def _looks_like_scoped_tafsir_query(text: str) -> bool:
    explicit_quran_scope = looks_like_explicit_quran_reference(text).get('matched', False)
    tafsir_scope = detect_tafsir_intent(text).get('matched', False)
    if explicit_quran_scope and tafsir_scope:
        return True
    lowered = text.casefold()
    return tafsir_scope and 'surah ' in lowered


def detect_topical_query_intent(query: str, *, allow_multi_source: bool = True) -> dict[str, Any]:
    text = normalize_user_query(query)
    if not text:
        return {
            'matched': False,
            'route_type': None,
            'topic_query': '',
            'signals': [],
            'reason': 'empty_query',
            'action_type': AskActionType.EXPLAIN.value,
        }

    if _looks_like_scoped_tafsir_query(text):
        return {
            'matched': False,
            'route_type': None,
            'topic_query': normalize_topic_query(text) or text,
            'signals': ['scoped_tafsir_query'],
            'reason': 'scoped_tafsir_query_detected',
            'action_type': AskActionType.EXPLAIN.value,
        }

    lowered = text.casefold()
    if allow_multi_source and any(prefix in lowered for prefix in _MIXED_MULTI_SOURCE_PREFIXES):
        return {
            'matched': True,
            'route_type': AskRouteType.TOPICAL_MULTI_SOURCE_QUERY.value,
            'topic_query': normalize_topic_query(text.replace('What does Islam say about', '').replace('what does islam say about', '')),
            'signals': ['topical_multi_source_query', 'normalized_topic_query'],
            'reason': 'topical_multi_source_query_detected',
            'action_type': AskActionType.EXPLAIN.value,
            'confidence': 0.7,
        }

    family = classify_query_family(text)
    hadith_concepts = link_query_to_concepts(text, domain='hadith', max_results=3)
    if family is not None and family.domain == 'hadith':
        topic_query = _topic_from_family(text, family, hadith_concepts)
        if family.needs_clarification:
            return {
                'matched': False,
                'route_type': None,
                'topic_query': topic_query,
                'signals': ['hadith_topic_needs_clarification'],
                'reason': 'broad_hadith_topic_requires_clarification',
                'action_type': AskActionType.EXPLAIN.value,
                'confidence': family.confidence,
                'query_profile': family.query_profile,
                'needs_clarification': True,
                'clarify_domain': 'hadith',
                'concept_matches': [match.slug for match in hadith_concepts],
            }
        if family.public_supported:
            return {
                'matched': True,
                'route_type': AskRouteType.TOPICAL_HADITH_QUERY.value,
                'topic_query': topic_query,
                'signals': ['topical_hadith_query', 'semantic_query_family', 'normalized_topic_query'],
                'reason': 'topical_hadith_query_detected',
                'action_type': AskActionType.EXPLAIN.value,
                'confidence': max(0.78, family.confidence),
                'query_profile': family.query_profile,
                'concept_matches': [match.slug for match in hadith_concepts],
            }

    quran_concepts = link_query_to_concepts(text, domain='quran_anchor', max_results=2)
    if family is not None and family.domain == 'tafsir' and quran_concepts:
        return {
            'matched': True,
            'route_type': AskRouteType.TOPICAL_TAFSIR_QUERY.value,
            'topic_query': _topic_from_family(text, family, quran_concepts),
            'signals': ['topical_tafsir_query', 'semantic_query_family', 'normalized_topic_query'],
            'reason': 'topical_tafsir_query_detected',
            'action_type': AskActionType.EXPLAIN.value,
            'confidence': max(0.74, family.confidence),
            'concept_matches': [match.slug for match in quran_concepts],
        }

    if family is not None and family.domain == 'tafsir' and family.public_supported:
        return {
            'matched': True,
            'route_type': AskRouteType.TOPICAL_TAFSIR_QUERY.value,
            'topic_query': _topic_from_family(text, family, quran_concepts),
            'signals': ['topical_tafsir_query', 'semantic_query_family', 'normalized_topic_query'],
            'reason': 'topical_tafsir_query_detected',
            'action_type': AskActionType.EXPLAIN.value,
            'confidence': max(0.74, family.confidence),
        }

    # Fallback — resolver-based safety net.
    #
    # The cue-phrase family classifier above is precise but conservative; it
    # rejects any query whose shape doesn't match an enumerated lead-in (e.g.
    # "How did the Prophet do ghusl?" matches no cue, so it would abstain
    # despite being a textbook topical hadith query).
    #
    # The taxonomy-backed resolver (domains.hadith_topical.query_topic_resolver)
    # already knows the vocabulary for all 182 leaf topics. If it finds a
    # confident primary_topic for this query, we trust that signal and route
    # to topical_hadith_query. This is belt-and-suspenders — the resolver
    # runs again inside the retrieval pipeline, so a false positive here is
    # cheap (retrieval still has the final word via its own word-boundary gate).
    resolution = resolve_topic(text, query_family=None)
    # Only treat the resolver-fallback as topical HADITH when the resolved
    # primary is NOT a quran/tafsir leaf — those belong to the tafsir lane.
    resolver_primary_family = (
        resolution.primary_topic.split('.', 1)[0] if resolution.primary_topic else None
    )
    if (
        resolution.primary_topic
        and resolution.confident_topics
        and resolver_primary_family not in {'quran', 'tafsir'}
    ):
        return {
            'matched': True,
            'route_type': AskRouteType.TOPICAL_HADITH_QUERY.value,
            'topic_query': normalize_topic_query(text) or text,
            'signals': ['topical_hadith_query', 'resolver_primary_topic'],
            'reason': 'topical_hadith_query_detected_via_resolver',
            'action_type': AskActionType.EXPLAIN.value,
            'confidence': 0.72,
            'query_profile': 'guidance',
            'concept_matches': list(resolution.confident_topics),
            'resolver_primary': resolution.primary_topic,
        }

    return {
        'matched': False,
        'route_type': None,
        'topic_query': normalize_topic_query(text) or text,
        'signals': [],
        'reason': 'no_supported_topical_query_pattern',
        'action_type': AskActionType.EXPLAIN.value,
    }
