from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from domains.query_intelligence.catalog import load_concept_definitions
from domains.query_intelligence.models import ConceptDefinition, ConceptMatch
from domains.query_intelligence.normalization import (
    normalize_compact_text,
    normalize_match_text,
    normalize_topic_query,
    tokenize_match_text,
)
from shared.utils.lexical import expand_query_tokens, trigram_similarity

_MATCHING_MODES = {'query', 'artifact_strict'}
_STOPWORDS = {
    'a', 'about', 'against', 'all', 'am', 'an', 'and', 'are', 'as', 'at', 'be', 'because', 'become', 'best',
    'by', 'can', 'come', 'control', 'did', 'do', 'does', 'for', 'from', 'get', 'good', 'how', 'i', 'in', 'into',
    'is', 'it', 'me', 'more', 'most', 'my', 'no', 'not', 'of', 'on', 'or', 'our', 'people', 'person', 'prophet',
    'said', 'say', 'should', 'show', 'so', 'someone', 'that', 'the', 'their', 'them', 'there',
    'these', 'they', 'this', 'to', 'very', 'was', 'we', 'what', 'when', 'who', 'why', 'will', 'with', 'you', 'your',
}


@dataclass(frozen=True, slots=True)
class _ConceptSurface:
    raw: str
    normalized: str
    compact: str
    tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ConceptIndexEntry:
    concept: ConceptDefinition
    query_surfaces: tuple[_ConceptSurface, ...]
    artifact_surfaces: tuple[_ConceptSurface, ...]
    all_tokens: tuple[str, ...]


@lru_cache(maxsize=1)
def _concept_index() -> tuple[_ConceptIndexEntry, ...]:
    entries: list[_ConceptIndexEntry] = []
    for concept in load_concept_definitions():
        base_surfaces = tuple(dict.fromkeys((concept.label_en, *concept.surface_forms)))
        query_surfaces = tuple(_build_surface(surface) for surface in base_surfaces if normalize_match_text(surface))
        if concept.artifact_surface_forms:
            artifact_source = concept.artifact_surface_forms
        else:
            artifact_source = tuple(
                surface for surface in base_surfaces
                if len(surface.split()) > 1 or len(normalize_compact_text(surface)) >= 5
            )
        artifact_surfaces = tuple(_build_surface(surface) for surface in artifact_source if normalize_match_text(surface))
        token_bag: list[str] = []
        seen_tokens: set[str] = set()
        for surface in (*query_surfaces, *artifact_surfaces):
            for token in surface.tokens:
                if token in seen_tokens or token in _STOPWORDS or len(token) < 3:
                    continue
                seen_tokens.add(token)
                token_bag.append(token)
        entries.append(
            _ConceptIndexEntry(
                concept=concept,
                query_surfaces=query_surfaces,
                artifact_surfaces=artifact_surfaces,
                all_tokens=tuple(token_bag),
            )
        )
    return tuple(entries)


@lru_cache(maxsize=4096)
def _build_surface(surface: str) -> _ConceptSurface:
    normalized = normalize_match_text(surface)
    return _ConceptSurface(
        raw=surface,
        normalized=normalized,
        compact=normalize_compact_text(surface),
        tokens=tokenize_match_text(surface),
    )


def _informative_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for token in expand_query_tokens(tokens):
        cleaned = normalize_match_text(token)
        if not cleaned or cleaned in seen or cleaned in _STOPWORDS or len(cleaned) < 3:
            continue
        seen.add(cleaned)
        values.append(cleaned)
    return tuple(values)


def _surface_score(surface: _ConceptSurface, query_text: str, query_compact: str, query_tokens: tuple[str, ...], matching_mode: str) -> tuple[float, list[str]]:
    matched_terms: list[str] = []
    score = 0.0
    if not surface.normalized:
        return 0.0, matched_terms

    if surface.normalized and surface.normalized in query_text:
        matched_terms.append(surface.raw.casefold())
        score = max(score, 0.94 if matching_mode == 'artifact_strict' else 0.91)
    elif surface.compact and len(surface.compact) >= 6 and surface.compact in query_compact:
        matched_terms.append(surface.raw.casefold())
        score = max(score, 0.9 if matching_mode == 'artifact_strict' else 0.87)

    if query_tokens and surface.tokens:
        overlap = sorted(set(query_tokens) & set(surface.tokens))
        if overlap:
            matched_terms.extend(overlap)
            coverage = len(overlap) / max(1, len(set(surface.tokens)))
            score = max(score, 0.5 + (0.34 * coverage))
        else:
            fuzzy_hits: list[str] = []
            best_similarity = 0.0
            for token in query_tokens:
                if len(token) < 4:
                    continue
                for candidate in surface.tokens:
                    if abs(len(candidate) - len(token)) > 4:
                        continue
                    similarity = trigram_similarity(token, candidate)
                    if similarity >= 0.52:
                        fuzzy_hits.append(token)
                        best_similarity = max(best_similarity, similarity)
                        break
            if fuzzy_hits:
                matched_terms.extend(fuzzy_hits)
                score = max(score, 0.46 + (0.28 * best_similarity))

    return min(score, 0.99), matched_terms


def link_query_to_concepts(
    query: str,
    *,
    domain: str | None = None,
    max_results: int = 3,
    matching_mode: str = 'query',
) -> list[ConceptMatch]:
    if matching_mode not in _MATCHING_MODES:
        raise ValueError(f'Unsupported matching_mode: {matching_mode}')

    normalized_query = normalize_match_text(query)
    if not normalized_query:
        return []
    normalized_topic = normalize_topic_query(query).casefold()
    query_compact = normalize_compact_text(query)
    query_tokens = _informative_tokens(tokenize_match_text(normalized_query))
    matches: list[tuple[float, ConceptMatch]] = []

    for entry in _concept_index():
        concept = entry.concept
        if domain is not None and concept.domain != domain:
            continue
        matched_terms: list[str] = []
        score = 0.0
        surfaces = entry.artifact_surfaces if matching_mode == 'artifact_strict' else entry.query_surfaces
        for surface in surfaces:
            surface_score, surface_terms = _surface_score(surface, normalized_query, query_compact, query_tokens, matching_mode)
            if surface_score > score:
                score = surface_score
            matched_terms.extend(surface_terms)

        if matching_mode == 'query' and score < 0.84 and query_tokens and entry.all_tokens:
            overlap = sorted(set(query_tokens) & set(entry.all_tokens))
            if overlap:
                matched_terms.extend(overlap)
                score = max(score, min(0.82, 0.44 + (0.13 * len(overlap))))
            elif normalized_topic:
                candidate_texts = [surface.normalized for surface in entry.query_surfaces if surface.normalized]
                if candidate_texts:
                    best_similarity = max(trigram_similarity(normalized_topic, candidate) for candidate in candidate_texts)
                    if best_similarity >= 0.52:
                        score = max(score, round(0.38 + (0.42 * best_similarity), 3))

        minimum_score = 0.84 if matching_mode == 'artifact_strict' else 0.48
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
