from __future__ import annotations

import re

from domains.hadith_topical.contracts import HadithTopicalQuery
from domains.hadith_topical.query_profile import infer_query_profile
from domains.query_intelligence.concept_linker import link_query_to_concepts
from domains.query_intelligence.normalization import normalize_topic_query

_WORD_RE = re.compile(r"[A-Za-z']+")


def normalize_hadith_topical_query(
    raw_query: str,
    *,
    language_hint: str | None = None,
    original_query: str | None = None,
) -> HadithTopicalQuery:
    normalized = normalize_topic_query(raw_query)
    tokens = tuple(match.group(0).casefold() for match in _WORD_RE.finditer(normalized))
    concept_matches = link_query_to_concepts(raw_query, domain='hadith', max_results=4)
    mapped_topics = tuple(match.slug for match in concept_matches)
    topic_family = concept_matches[0].family if concept_matches else None
    directive_biases = concept_matches[0].directive_biases if concept_matches else ()
    profile = infer_query_profile(raw_query)
    debug = {
        'tokens': tokens,
        'mapped_topics': mapped_topics,
        'topic_family': topic_family,
        'directive_biases': directive_biases,
        'profile': profile,
        'concept_matches': [
            {
                'concept_id': match.concept_id,
                'slug': match.slug,
                'confidence': match.confidence,
                'matched_terms': list(match.matched_terms),
            }
            for match in concept_matches
        ],
    }
    return HadithTopicalQuery(
        raw_query=raw_query,
        normalized_query=normalized,
        topic_candidates=mapped_topics,
        query_profile=profile,
        language_hint=language_hint,
        topic_family=topic_family,
        directive_biases=tuple(directive_biases),
        debug=debug,
        original_query=original_query,
    )
