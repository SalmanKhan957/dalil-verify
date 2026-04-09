from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from domains.hadith.contracts import HadithLexicalHit
from domains.hadith.service import HadithService
from domains.hadith_topical.contracts import (
    HadithTopicalCandidate,
    HadithTopicalCandidateGenerationRequest,
    HadithTopicalCandidateGenerationResult,
)
from domains.hadith_topical.enricher import build_enriched_document
from infrastructure.search.index_names import HADITH_TOPICAL_INDEX
from infrastructure.search.opensearch.hadith_topical_queries import build_hadith_topical_bm25_query
from infrastructure.search.opensearch_client import OpenSearchClient


def _collection_slug_from_source_id(source_id: str) -> str:
    return source_id.replace('hadith:', '')


def _incidental_penalty(flags: tuple[str, ...]) -> float:
    if 'incidental_mention_risk' in flags:
        return 0.5
    if 'narrative_specific_risk' in flags:
        return 0.35
    if flags:
        return 0.2
    return 0.0


def _dedupe_candidates(candidates: Iterable[HadithTopicalCandidate]) -> tuple[HadithTopicalCandidate, ...]:
    deduped: dict[str, HadithTopicalCandidate] = {}
    for candidate in candidates:
        existing = deduped.get(candidate.canonical_ref)
        if existing is None:
            deduped[candidate.canonical_ref] = candidate
            continue
        existing_score = float(existing.rerank_score or existing.fusion_score or existing.lexical_score or 0.0)
        candidate_score = float(candidate.rerank_score or candidate.fusion_score or candidate.lexical_score or 0.0)
        if candidate_score > existing_score:
            deduped[candidate.canonical_ref] = candidate
    return tuple(deduped.values())


def candidate_from_lexical_hit(query_topics: tuple[str, ...], hit: HadithLexicalHit) -> HadithTopicalCandidate:
    entry = hit.entry
    enriched = build_enriched_document(
        canonical_ref=entry.canonical_ref_collection,
        collection_source_id=entry.collection_source_id,
        collection_slug=_collection_slug_from_source_id(entry.collection_source_id),
        collection_hadith_number=entry.collection_hadith_number,
        book_number=entry.book_number,
        chapter_number=entry.chapter_number,
        numbering_quality='collection_number_stable',
        english_text=str(entry.english_text or ''),
        arabic_text=entry.arabic_text,
        english_narrator=entry.english_narrator,
        book_title_en=hit.book_title,
        chapter_title_en=hit.chapter_title,
    )
    matched_topics = tuple(topic for topic in query_topics if topic in set(enriched.topic_tags) | set(enriched.normalized_topic_terms))
    matched_terms = tuple(dict.fromkeys(tuple(hit.matched_terms or ()) + tuple(matched_topics)))
    score = float(hit.rank_score if hit.rank_score is not None else hit.score)
    return HadithTopicalCandidate(
        canonical_ref=entry.canonical_ref_collection,
        source_id=entry.collection_source_id,
        retrieval_origin='lexical_db_fallback',
        lexical_score=score,
        fusion_score=score,
        central_topic_score=enriched.central_topic_score,
        answerability_score=enriched.answerability_score,
        narrative_specificity_score=enriched.narrative_specificity_score,
        incidental_topic_penalty=_incidental_penalty(enriched.incidental_topic_flags),
        guidance_role=enriched.guidance_role,
        topic_family=enriched.topic_family,
        matched_topics=matched_topics,
        matched_terms=matched_terms,
        metadata={
            'snippet': hit.snippet,
            'display_name': hit.display_name,
            'citation_label': hit.citation_label,
            'retrieval_method': hit.retrieval_method,
            'book_title_en': hit.book_title,
            'chapter_title_en': hit.chapter_title,
            'english_text': entry.english_text,
            'english_narrator': entry.english_narrator,
            'contextual_summary': enriched.contextual_summary,
            'topic_tags': list(enriched.topic_tags),
            'directive_labels': list(enriched.directive_labels),
            'normalized_topic_terms': list(enriched.normalized_topic_terms),
            'incidental_topic_flags': list(enriched.incidental_topic_flags),
            'guidance_role': enriched.guidance_role,
            'topic_family': enriched.topic_family,
            'answerability_score': enriched.answerability_score,
            'narrative_specificity_score': enriched.narrative_specificity_score,
            'moral_concepts': list(enriched.moral_concepts),
        },
    )


def _candidate_from_opensearch_source(query_topics: tuple[str, ...], source: dict[str, Any], *, score: float, retrieval_origin: str) -> HadithTopicalCandidate:
    topic_tags = tuple(source.get('topic_tags') or ())
    normalized_topic_terms = tuple(source.get('normalized_topic_terms') or ())
    incidental_flags = tuple(source.get('incidental_topic_flags') or ())
    matched_topics = tuple(topic for topic in query_topics if topic in set(topic_tags) | set(normalized_topic_terms))
    matched_terms = tuple(dict.fromkeys(tuple(source.get('normalized_alias_terms') or ()) + tuple(matched_topics)))
    return HadithTopicalCandidate(
        canonical_ref=str(source.get('canonical_ref') or ''),
        source_id=str(source.get('collection_source_id') or ''),
        retrieval_origin=retrieval_origin,
        lexical_score=score,
        fusion_score=score,
        central_topic_score=float(source.get('central_topic_score') or 0.0),
        answerability_score=float(source.get('answerability_score') or 0.0),
        narrative_specificity_score=float(source.get('narrative_specificity_score') or 0.0),
        incidental_topic_penalty=_incidental_penalty(incidental_flags),
        guidance_role=str(source.get('guidance_role') or '') or None,
        topic_family=str(source.get('topic_family') or '') or None,
        matched_topics=matched_topics,
        matched_terms=matched_terms,
        metadata={
            'snippet': source.get('contextual_summary') or source.get('english_text'),
            'english_text': source.get('english_text'),
            'english_narrator': source.get('english_narrator'),
            'contextual_summary': source.get('contextual_summary'),
            'book_title_en': source.get('book_title_en'),
            'chapter_title_en': source.get('chapter_title_en'),
            'topic_tags': list(topic_tags),
            'directive_labels': list(source.get('directive_labels') or ()),
            'normalized_topic_terms': list(normalized_topic_terms),
            'incidental_topic_flags': list(incidental_flags),
            'guidance_role': source.get('guidance_role'),
            'topic_family': source.get('topic_family'),
            'answerability_score': float(source.get('answerability_score') or 0.0),
            'narrative_specificity_score': float(source.get('narrative_specificity_score') or 0.0),
            'moral_concepts': list(source.get('moral_concepts') or ()),
        },
    )


class HadithTopicalCandidateGenerator:
    def __init__(self, *, database_url: str | None = None, opensearch_client: OpenSearchClient | None = None) -> None:
        self.database_url = database_url
        self.opensearch_client = opensearch_client or OpenSearchClient.from_environment()

    def generate(
        self,
        request: HadithTopicalCandidateGenerationRequest,
        *,
        lexical_hits: list[HadithLexicalHit] | None = None,
    ) -> HadithTopicalCandidateGenerationResult:
        warnings: list[str] = []
        debug: dict[str, Any] = {
            'candidate_limit': request.candidate_limit,
            'lexical_limit': request.lexical_limit,
            'collection_source_id': request.collection_source_id,
            'topic_family': request.query.topic_family,
            'directive_biases': list(request.query.directive_biases),
        }
        if lexical_hits is None:
            lexical_hits = self._load_lexical_hits(request)
            debug['lexical_hits_source'] = 'runtime_lookup'
        else:
            debug['lexical_hits_source'] = 'prefetched_shadow_baseline'
        lexical_candidates = tuple(candidate_from_lexical_hit(request.query.topic_candidates, hit) for hit in lexical_hits)
        candidates = list(lexical_candidates)
        debug['lexical_candidate_count'] = len(lexical_candidates)

        opensearch_candidates: tuple[HadithTopicalCandidate, ...] = ()
        if request.allow_opensearch and self.opensearch_client.is_enabled:
            try:
                opensearch_candidates = self._load_opensearch_candidates(request)
                candidates.extend(opensearch_candidates)
                debug['opensearch_candidate_count'] = len(opensearch_candidates)
            except Exception as exc:  # pragma: no cover - network path is integration-only
                warnings.append('hadith_topical_opensearch_unavailable')
                debug['opensearch_error'] = str(exc)
        else:
            debug['opensearch_candidate_count'] = 0
            if request.allow_opensearch:
                warnings.append('hadith_topical_opensearch_not_configured')

        deduped = list(_dedupe_candidates(candidates))
        deduped.sort(
            key=lambda item: (
                -float(item.fusion_score or item.lexical_score or 0.0),
                -float(item.answerability_score or 0.0),
                -float(item.central_topic_score or 0.0),
                float(item.incidental_topic_penalty or 0.0),
                float(item.narrative_specificity_score or 0.0),
                item.canonical_ref,
            )
        )
        selected = tuple(deduped[: max(1, int(request.candidate_limit))])
        debug['candidate_count'] = len(selected)
        debug['candidate_origins'] = [candidate.retrieval_origin for candidate in selected]
        return HadithTopicalCandidateGenerationResult(candidates=selected, warnings=tuple(dict.fromkeys(warnings)), debug=debug)

    def _load_lexical_hits(self, request: HadithTopicalCandidateGenerationRequest) -> list[HadithLexicalHit]:
        service = HadithService(database_url=self.database_url)
        return service.search_topically(
            query_text=request.query.normalized_query or request.query.raw_query,
            collection_source_id=request.collection_source_id,
            limit=max(1, int(request.lexical_limit)),
        )

    def _load_opensearch_candidates(self, request: HadithTopicalCandidateGenerationRequest) -> tuple[HadithTopicalCandidate, ...]:
        query = build_hadith_topical_bm25_query(
            request.query,
            collection_source_id=request.collection_source_id,
            size=max(10, int(request.candidate_limit) * 3),
        )
        response = self.opensearch_client.search(index=HADITH_TOPICAL_INDEX, body=query)
        hits = (((response or {}).get('hits') or {}).get('hits') or [])
        candidates: list[HadithTopicalCandidate] = []
        for hit in hits:
            source = hit.get('_source') or {}
            canonical_ref = str(source.get('canonical_ref') or '').strip()
            if not canonical_ref:
                continue
            candidates.append(
                _candidate_from_opensearch_source(
                    request.query.topic_candidates,
                    source,
                    score=float(hit.get('_score') or 0.0),
                    retrieval_origin='opensearch_bm25',
                )
            )
        return tuple(candidates)
