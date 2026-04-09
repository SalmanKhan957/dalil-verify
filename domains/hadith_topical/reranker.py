from __future__ import annotations

import re
from dataclasses import replace

from domains.hadith_topical.contracts import HadithTopicalCandidate, HadithTopicalQuery
from infrastructure.rerank.provider import RerankProvider

_TOKEN_RE = re.compile(r"[A-Za-z']+")


def _tokens(text: str | None) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(text or '')}


def _overlap_score(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    denom = max(1, min(len(a), len(b)))
    return inter / denom


def _preferred_role_bonus(query: HadithTopicalQuery, candidate: HadithTopicalCandidate) -> float:
    role = candidate.guidance_role or ''
    profile = query.query_profile
    if profile == 'prophetic_guidance':
        return 0.18 if role in {'direct_moral_instruction', 'virtue_statement', 'warning'} else (-0.1 if role == 'narrative_incident' else 0.0)
    if profile == 'warning':
        return 0.16 if role in {'warning', 'direct_moral_instruction'} else (-0.08 if role == 'narrative_incident' else 0.0)
    if profile == 'virtue':
        return 0.16 if role == 'virtue_statement' else (-0.08 if role == 'narrative_incident' else 0.0)
    if profile == 'guidance':
        return 0.1 if role in {'direct_moral_instruction', 'virtue_statement', 'warning'} else (-0.06 if role == 'narrative_incident' else 0.0)
    return 0.0


def _heuristic_rerank_score(query: HadithTopicalQuery, candidate: HadithTopicalCandidate) -> float:
    metadata = dict(candidate.metadata or {})
    query_tokens = _tokens(query.normalized_query or query.raw_query)
    chapter_tokens = _tokens(metadata.get('chapter_title_en'))
    summary_tokens = _tokens(metadata.get('contextual_summary') or metadata.get('snippet'))
    text_tokens = _tokens(metadata.get('english_text'))
    concept_aligned = bool(set(candidate.matched_topics or ()) & set(query.topic_candidates or ()))
    matched_topic_bonus = 0.18 if concept_aligned else 0.0
    matched_term_bonus = 0.12 if candidate.matched_terms else 0.0
    concept_miss_penalty = 0.12 if (query.topic_candidates and not concept_aligned) else 0.0
    chapter_overlap = _overlap_score(query_tokens, chapter_tokens)
    summary_overlap = _overlap_score(query_tokens, summary_tokens)
    text_overlap = _overlap_score(query_tokens, text_tokens)
    centrality = float(candidate.central_topic_score or 0.0)
    answerability = float(candidate.answerability_score or 0.0)
    incidental_penalty = float(candidate.incidental_topic_penalty or 0.0)
    narrative_specificity = float(candidate.narrative_specificity_score or 0.0)
    score = (
        0.24 * chapter_overlap
        + 0.16 * summary_overlap
        + 0.1 * text_overlap
        + 0.16 * centrality
        + 0.18 * answerability
        + matched_topic_bonus
        + matched_term_bonus
        + _preferred_role_bonus(query, candidate)
        - concept_miss_penalty
        - 0.12 * incidental_penalty
        - 0.1 * narrative_specificity
    )
    return max(0.0, min(score, 1.0))


class NoOpHadithTopicalReranker:
    def __init__(self, provider: RerankProvider | None = None, *, provider_weight: float = 0.45) -> None:
        self.provider = provider
        self.provider_weight = max(0.0, min(provider_weight, 0.8))

    def rerank(self, query: HadithTopicalQuery, candidates: list[HadithTopicalCandidate]) -> list[HadithTopicalCandidate]:
        if not candidates:
            return candidates
        heuristic_scores = [_heuristic_rerank_score(query, candidate) for candidate in candidates]
        provider_scores: list[float] | None = None
        if self.provider is not None:
            documents = [self._document_text(candidate) for candidate in candidates]
            raw_scores = [float(score) for score in self.provider.rerank(query.normalized_query or query.raw_query, documents)]
            max_score = max(raw_scores) if raw_scores else 0.0
            provider_scores = [score / max_score if max_score > 1e-9 else 0.0 for score in raw_scores]
        reranked: list[HadithTopicalCandidate] = []
        for index, candidate in enumerate(candidates):
            heuristic = heuristic_scores[index]
            if provider_scores is None:
                final_score = heuristic
            else:
                final_score = ((1.0 - self.provider_weight) * heuristic) + (self.provider_weight * provider_scores[index])
            reranked.append(replace(candidate, rerank_score=round(max(0.0, min(final_score, 1.0)), 4)))
        return reranked

    @staticmethod
    def _document_text(candidate: HadithTopicalCandidate) -> str:
        metadata = candidate.metadata or {}
        parts = [
            str(metadata.get('chapter_title_en') or ''),
            str(metadata.get('contextual_summary') or ''),
            str(metadata.get('english_text') or ''),
            str(metadata.get('book_title_en') or ''),
        ]
        return ' '.join(part for part in parts if part).strip()
