from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache

from domains.query_intelligence.catalog import load_concept_definitions
from domains.query_intelligence.models import ConceptDefinition, ConceptMatch
from domains.query_intelligence.normalization import normalize_topic_query, normalize_user_query

_TOKEN_RE = re.compile(r"[A-Za-z']+")
_MATCHING_MODES = {'query', 'artifact_strict'}
_STOPWORDS = {
    'a', 'about', 'against', 'all', 'am', 'an', 'and', 'are', 'as', 'at', 'be', 'because', 'become', 'best',
    'by', 'can', 'come', 'control', 'did', 'do', 'does', 'for', 'from', 'get', 'good', 'how', 'i', 'in', 'into',
    'is', 'it', 'me', 'more', 'most', 'my', 'no', 'not', 'of', 'on', 'or', 'our', 'people', 'person', 'prophet',
    'restrain', 'said', 'say', 'should', 'show', 'so', 'someone', 'that', 'the', 'their', 'them', 'there',
    'these', 'they', 'this', 'to', 'very', 'was', 'we', 'what', 'when', 'who', 'why', 'will', 'with', 'you', 'your',
}


@lru_cache(maxsize=512)
def _surface_pattern(surface: str) -> re.Pattern[str]:
    escaped = re.escape(surface.strip())
    return re.compile(rf'(?<![A-Za-z]){escaped}(?![A-Za-z])', re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(text or '')}


def _informative_tokens(text: str) -> set[str]:
    tokens = _tokens(text)
    return {token for token in tokens if len(token) >= 4 and token not in _STOPWORDS}


def _match_surface(surface: str, normalized_query: str) -> bool:
    surface = surface.strip().casefold()
    if not surface:
        return False
    return _surface_pattern(surface).search(normalized_query) is not None


def _surfaces_for_mode(concept: ConceptDefinition, matching_mode: str) -> tuple[str, ...]:
    base = (concept.label_en.casefold(), *concept.surface_forms)
    if matching_mode == 'artifact_strict':
        strict = tuple(value for value in concept.artifact_surface_forms if value)
        if strict:
            return strict
        return tuple(
            dict.fromkeys(
                surface for surface in base
                if len(surface.split()) > 1 or len(surface.replace(' ', '')) >= 5
            )
        )
    return tuple(dict.fromkeys(base))


def link_query_to_concepts(
    query: str,
    *,
    domain: str | None = None,
    max_results: int = 3,
    matching_mode: str = 'query',
) -> list[ConceptMatch]:
    if matching_mode not in _MATCHING_MODES:
        raise ValueError(f'Unsupported matching_mode: {matching_mode}')
    normalized_query = normalize_user_query(query).casefold()
    normalized_topic = normalize_topic_query(query).casefold()
    query_tokens = _tokens(normalized_query)
    query_informative_tokens = _informative_tokens(normalized_query)
    matches: list[tuple[float, ConceptMatch]] = []
    for concept in load_concept_definitions():
        if domain is not None and concept.domain != domain:
            continue
        matched_terms: list[str] = []
        score = 0.0
        surfaces = _surfaces_for_mode(concept, matching_mode)
        for surface in surfaces:
            if _match_surface(surface, normalized_query):
                matched_terms.append(surface)
                if surface == concept.label_en.casefold():
                    score = max(score, 0.92 if matching_mode == 'artifact_strict' else 0.9)
                elif len(surface.split()) > 1:
                    score = max(score, 0.9 if matching_mode == 'artifact_strict' else 0.86)
                else:
                    score = max(score, 0.88 if matching_mode == 'artifact_strict' else 0.84)
        if score < 0.84 and matching_mode == 'query':
            concept_tokens = _informative_tokens(' '.join((concept.label_en.casefold(), *concept.surface_forms, *concept.artifact_surface_forms)))
            overlap_terms = sorted(query_informative_tokens & concept_tokens)
            overlap = len(overlap_terms)
            if overlap:
                score = max(score, min(0.78, 0.46 + (0.12 * overlap)))
                matched_terms.extend(overlap_terms)
            elif normalized_topic:
                similarity = max(
                    SequenceMatcher(a=normalized_topic, b=surface).ratio()
                    for surface in tuple(dict.fromkeys((concept.label_en.casefold(), *concept.surface_forms)))
                )
                if similarity >= 0.72:
                    score = max(score, round(0.42 + (0.3 * similarity), 3))
        minimum_score = 0.84 if matching_mode == 'artifact_strict' else 0.45
        if score < minimum_score:
            continue
        matches.append(
            (
                score,
                ConceptMatch(
                    concept_id=concept.concept_id,
                    slug=concept.slug,
                    domain=concept.domain,
                    family=concept.family,
                    confidence=round(min(score, 0.99), 3),
                    matched_terms=tuple(dict.fromkeys(matched_terms)),
                    directive_biases=concept.directive_biases,
                    guidance_roles=concept.guidance_roles,
                    canonical_ref=concept.canonical_ref,
                    debug={
                        'normalized_query': normalized_query,
                        'normalized_topic': normalized_topic,
                        'matching_mode': matching_mode,
                    },
                ),
            )
        )
    matches.sort(key=lambda item: (-item[0], -len(item[1].matched_terms), item[1].concept_id))
    return [match for _, match in matches[: max(1, int(max_results))]]
