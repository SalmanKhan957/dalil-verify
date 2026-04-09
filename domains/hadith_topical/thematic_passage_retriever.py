from __future__ import annotations

from typing import Any

from domains.hadith.contracts import HadithLexicalHit
from domains.hadith.types import HadithEntryRecord
from domains.hadith_topical.contracts import HadithTopicalCandidate, HadithTopicalQuery
from domains.hadith_topical.query_family_classifier import HadithTopicFamilyDecision
from infrastructure.search.hadith_topical_hybrid import fuse_lexical_and_semantic, score_text_against_query
from shared.utils.lexical import normalize_search_text, tokenize_search_text

_GENERIC_QUERY_TOKENS = {'prophet', 'said', 'say', 'coming', 'come', 'about', 'what'}


def _tokens(text: str | None) -> set[str]:
    return set(tokenize_search_text(text or ''))


def _lexical_rank_value(hit: HadithLexicalHit) -> float:
    return float(getattr(hit, 'rank_score', None) if getattr(hit, 'rank_score', None) is not None else (getattr(hit, 'score', 0.0) or 0.0))


def _candidate_from_hit(query: HadithTopicalQuery, hit: HadithLexicalHit, *, family_decision: HadithTopicFamilyDecision, alias_hits: tuple[str, ...], content_overlap: tuple[str, ...], title_alias_hit: bool, score: float, semantic_score: float) -> HadithTopicalCandidate:
    entry: HadithEntryRecord = hit.entry
    matched_topics_seed = list(query.topic_candidates or ())
    if family_decision.entity_slug:
        matched_topics_seed.append(family_decision.entity_slug)
    matched_topics_seed.extend(alias_hits)
    matched_topics = tuple(dict.fromkeys(value for value in matched_topics_seed if value))
    matched_terms = tuple(dict.fromkeys((*alias_hits, *content_overlap)))
    metadata = {
        'snippet': getattr(hit, 'snippet', None),
        'english_text': getattr(entry, 'english_text', None),
        'english_narrator': getattr(entry, 'english_narrator', None),
        'book_title_en': getattr(hit, 'book_title', None),
        'chapter_title_en': getattr(hit, 'chapter_title', None),
        'family_id': family_decision.family_id,
        'entity_slug': family_decision.entity_slug,
        'thematic_passage': True,
        'alias_hits': list(alias_hits),
        'content_overlap': list(content_overlap),
        'title_alias_hit': title_alias_hit,
    }
    return HadithTopicalCandidate(
        canonical_ref=entry.canonical_ref_collection,
        source_id=entry.collection_source_id,
        retrieval_origin='thematic_passage_hybrid' if semantic_score >= 0.22 else 'thematic_passage_lexical',
        lexical_score=_lexical_rank_value(hit),
        vector_score=round(semantic_score, 4),
        fusion_score=round(score, 4),
        rerank_score=round(score, 4),
        central_topic_score=round(max(score, 0.45 if alias_hits else 0.0), 3),
        answerability_score=round(min(1.0, 0.52 + (0.22 if alias_hits else 0.0) + (0.08 if title_alias_hit else 0.0)), 3),
        narrative_specificity_score=0.22,
        incidental_topic_penalty=0.04 if alias_hits else 0.16,
        guidance_role='thematic_passage',
        topic_family=family_decision.family_id,
        matched_topics=matched_topics,
        matched_terms=matched_terms,
        metadata=metadata,
    )


class HadithThematicPassageRetriever:
    """Retrieve fuller thematic passages for entity/event/ritual topical hadith asks."""

    def __init__(self, *, database_url: str | None = None) -> None:
        self.database_url = database_url

    def retrieve(
        self,
        *,
        query: HadithTopicalQuery,
        family_decision: HadithTopicFamilyDecision,
        collection_source_id: str | None = None,
        lexical_hits: list[HadithLexicalHit] | None = None,
        limit: int = 8,
    ) -> tuple[list[HadithTopicalCandidate], dict[str, Any]]:
        if lexical_hits is None:
            from domains.hadith.service import HadithService
            service = HadithService(database_url=self.database_url)
            lexical_hits = service.search_topically(
                query_text=query.normalized_query or query.raw_query,
                collection_source_id=collection_source_id,
                limit=max(limit * 6, 24),
            )
            lexical_source = 'runtime_lookup'
        else:
            lexical_source = 'prefetched'
        alias_terms = tuple(normalize_search_text(value) for value in family_decision.matched_aliases if normalize_search_text(value))
        content_query_tokens = tuple(token for token in tokenize_search_text(query.normalized_query or query.raw_query) if token not in _GENERIC_QUERY_TOKENS)
        debug: dict[str, Any] = {
            'family_id': family_decision.family_id,
            'retrieval_strategy': family_decision.retrieval_strategy,
            'matched_aliases': list(alias_terms),
            'entity_slug': family_decision.entity_slug,
            'lexical_hits_source': lexical_source,
            'lexical_hit_count': len(lexical_hits),
        }
        scored: list[tuple[float, HadithTopicalCandidate]] = []
        rejected: list[dict[str, object]] = []
        for hit in lexical_hits:
            entry = getattr(hit, 'entry', None)
            if entry is None:
                continue
            search_space = normalize_search_text(' '.join(filter(None, [
                getattr(entry, 'english_text', None),
                getattr(entry, 'english_narrator', None),
                getattr(hit, 'snippet', None),
                getattr(hit, 'book_title', None),
                getattr(hit, 'chapter_title', None),
            ])))
            hit_tokens = _tokens(search_space)
            alias_hits = tuple(alias for alias in alias_terms if alias in search_space)
            content_overlap = tuple(token for token in content_query_tokens if token in hit_tokens)
            title_space = normalize_search_text(' '.join(filter(None, [getattr(hit, 'book_title', None), getattr(hit, 'chapter_title', None)])))
            title_alias_hit = any(alias in title_space for alias in alias_terms)
            semantic = score_text_against_query(
                query_text=query.normalized_query or query.raw_query,
                document_text=' '.join(filter(None, [search_space, title_space])),
                alias_terms=alias_terms,
            )
            if family_decision.family_id in {'entity_eschatology', 'narrative_event'} and not alias_hits and semantic.semantic_score < 0.32:
                rejected.append({'canonical_ref': entry.canonical_ref_collection, 'reason': 'entity_alias_or_semantic_match_missing'})
                continue
            if not alias_hits and len(content_overlap) < 2 and semantic.semantic_score < 0.28:
                rejected.append({'canonical_ref': entry.canonical_ref_collection, 'reason': 'weak_content_overlap'})
                continue
            lexical_rank = _lexical_rank_value(hit)
            lexical_rank = lexical_rank / (lexical_rank + 4.0) if lexical_rank > 1.0 else lexical_rank
            alias_score = min(1.0, 0.34 + (0.24 * len(alias_hits))) if alias_hits else 0.0
            overlap_ratio = min(len(content_overlap) / max(len(content_query_tokens), 1), 1.0)
            fused_rank = fuse_lexical_and_semantic(lexical_score=lexical_rank, semantic_score=semantic.semantic_score, semantic_weight=0.36)
            score = (
                0.28 * alias_score
                + 0.16 * overlap_ratio
                + 0.16 * lexical_rank
                + 0.18 * semantic.semantic_score
                + 0.12 * fused_rank
                + (0.08 if title_alias_hit else 0.0)
                + (0.08 if family_decision.family_id == 'ritual_practice' and any(token in {'prayer', 'fasting', 'wudu', 'zakat', 'sick', 'illness'} for token in content_overlap) else 0.0)
            )
            if score < 0.34:
                rejected.append({'canonical_ref': entry.canonical_ref_collection, 'reason': 'score_below_threshold', 'score': round(score, 3)})
                continue
            candidate = _candidate_from_hit(query, hit, family_decision=family_decision, alias_hits=alias_hits, content_overlap=content_overlap, title_alias_hit=title_alias_hit, score=score, semantic_score=semantic.semantic_score)
            scored.append((score, candidate))
        scored.sort(key=lambda item: (-item[0], -float(item[1].answerability_score or 0.0), item[1].canonical_ref))
        chosen: list[HadithTopicalCandidate] = []
        seen_refs: set[str] = set()
        for _score, candidate in scored:
            if candidate.canonical_ref in seen_refs:
                continue
            chosen.append(candidate)
            seen_refs.add(candidate.canonical_ref)
            if len(chosen) >= max(1, int(limit)):
                break
        debug['candidate_count'] = len(chosen)
        debug['rejected_preview'] = rejected[:10]
        return chosen, debug
