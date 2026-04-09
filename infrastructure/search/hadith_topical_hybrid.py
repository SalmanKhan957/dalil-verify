from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log, sqrt
from typing import Iterable

from shared.utils.lexical import expand_query_tokens, normalize_search_text, tokenize_search_text, trigram_similarity

_GENERIC_QUERY_TOKENS = {
    'prophet', 'said', 'say', 'what', 'about', 'give', 'tell', 'coming', 'come',
    'did', 'the', 'of', 'hour', 'signs', 'sign',
}


@dataclass(frozen=True, slots=True)
class HybridScoredMatch:
    semantic_score: float
    lexical_overlap_ratio: float
    matched_terms: tuple[str, ...]


def _significant_query_tokens(query_text: str) -> list[str]:
    tokens = tokenize_search_text(query_text)
    expanded = expand_query_tokens(tokens)
    seen: set[str] = set()
    filtered: list[str] = []
    for token in expanded:
        normalized = normalize_search_text(token)
        if not normalized or normalized in _GENERIC_QUERY_TOKENS:
            continue
        if normalized not in seen:
            filtered.append(normalized)
            seen.add(normalized)
    return filtered


def _idf_weights(query_tokens: list[str], document_token_sets: list[set[str]]) -> dict[str, float]:
    total_docs = max(len(document_token_sets), 1)
    weights: dict[str, float] = {}
    for token in query_tokens:
        doc_freq = sum(1 for token_set in document_token_sets if token in token_set)
        weights[token] = 1.0 + log((1.0 + total_docs) / (1.0 + doc_freq))
    return weights


def score_text_against_query(
    *,
    query_text: str,
    document_text: str,
    alias_terms: Iterable[str] = (),
) -> HybridScoredMatch:
    normalized_doc = normalize_search_text(document_text)
    if not normalized_doc:
        return HybridScoredMatch(semantic_score=0.0, lexical_overlap_ratio=0.0, matched_terms=())
    query_tokens = _significant_query_tokens(query_text)
    document_tokens = tokenize_search_text(normalized_doc)
    document_token_set = set(document_tokens)
    if not query_tokens:
        return HybridScoredMatch(semantic_score=0.0, lexical_overlap_ratio=0.0, matched_terms=())

    idf = _idf_weights(query_tokens, [document_token_set])
    overlap_terms: list[str] = []
    weighted_overlap = 0.0
    weighted_total = 0.0
    for token in query_tokens:
        weight = idf[token]
        weighted_total += weight
        if token in document_token_set or token in normalized_doc:
            overlap_terms.append(token)
            weighted_overlap += weight
    lexical_overlap_ratio = weighted_overlap / weighted_total if weighted_total else 0.0

    alias_hits = [alias for alias in alias_terms if alias and normalize_search_text(alias) in normalized_doc]
    alias_bonus = min(0.32, 0.12 * len(alias_hits))
    fuzzy_bonus = 0.0
    if lexical_overlap_ratio < 0.99:
        best = 0.0
        for token in query_tokens:
            for doc_token in list(document_token_set)[:80]:
                score = trigram_similarity(token, doc_token)
                if score > best:
                    best = score
        if best >= 0.42:
            fuzzy_bonus = min(0.18, best * 0.22)

    semantic_score = max(0.0, min(1.0, 0.68 * lexical_overlap_ratio + alias_bonus + fuzzy_bonus))
    matched_terms = tuple(dict.fromkeys([*alias_hits, *overlap_terms]))
    return HybridScoredMatch(
        semantic_score=round(semantic_score, 4),
        lexical_overlap_ratio=round(lexical_overlap_ratio, 4),
        matched_terms=matched_terms,
    )


def fuse_lexical_and_semantic(*, lexical_score: float | None, semantic_score: float | None, semantic_weight: float = 0.34) -> float:
    lexical_value = float(lexical_score or 0.0)
    if lexical_value > 1.0:
        lexical_value = lexical_value / (lexical_value + 4.0)
    semantic_value = float(semantic_score or 0.0)
    lexical_weight = max(0.0, min(1.0, 1.0 - semantic_weight))
    return round((lexical_weight * lexical_value) + (semantic_weight * semantic_value), 4)
