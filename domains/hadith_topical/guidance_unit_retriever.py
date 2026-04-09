from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from domains.hadith_topical.contracts import HadithTopicalCandidate, HadithTopicalQuery
from domains.hadith_topical.guidance_unit_models import GuidanceUnitDocument
from infrastructure.search.hadith_topical_hybrid import fuse_lexical_and_semantic, score_text_against_query
from infrastructure.search.index_names import HADITH_GUIDANCE_UNIT_INDEX
from infrastructure.search.opensearch.hadith_guidance_unit_queries import build_hadith_guidance_bm25_query
from infrastructure.search.opensearch_client import OpenSearchClient

_TOKEN_RE = re.compile(r"[A-Za-z']+")
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ARTIFACT_PATHS = (
    _REPO_ROOT / 'artifacts' / 'hadith_topical' / 'guidance_units.v1.jsonl',
    _REPO_ROOT / 'data' / 'processed' / 'hadith_topical' / 'guidance_units.v1.jsonl',
)


def _tokens(text: str | None) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(text or '')}


def _normalized_role(role: str | None) -> str:
    value = str(role or '').strip() or 'narrative_incident'
    if value == 'narrative_context':
        return 'narrative_incident'
    return value


def _topic_alignment(query: HadithTopicalQuery, doc: GuidanceUnitDocument) -> tuple[tuple[str, ...], int, int]:
    query_topics = tuple(query.topic_candidates or ())
    central = set(doc.central_concept_ids or ())
    secondary = set(doc.secondary_concept_ids or ())
    matched_topics = tuple(topic for topic in query_topics if topic in central or topic in secondary)
    concept_alignment = sum(1 for topic in query_topics if topic in central)
    secondary_alignment = sum(1 for topic in query_topics if topic in secondary and topic not in central)
    return matched_topics, concept_alignment, secondary_alignment


def _central_topic_score(
    query: HadithTopicalQuery,
    doc: GuidanceUnitDocument,
    *,
    lexical_overlap_ratio: float = 0.0,
) -> tuple[float, tuple[str, ...], int, int]:
    matched_topics, concept_alignment, secondary_alignment = _topic_alignment(query, doc)
    directness = max(0.0, min(float(doc.directness_score or 0.0), 1.0))
    answerability = max(0.0, min(float(doc.answerability_score or 0.0), 1.0))
    builder_rank = max(0.0, min(float((doc.metadata or {}).get('builder_rank_score') or 0.0), 1.0))
    concept_signal = 1.0 if concept_alignment else (0.58 if secondary_alignment else 0.0)
    centrality = (
        0.46 * concept_signal
        + 0.22 * directness
        + 0.14 * answerability
        + 0.12 * builder_rank
        + 0.06 * max(0.0, min(lexical_overlap_ratio, 1.0))
    )
    if _normalized_role(doc.guidance_role) == 'narrative_incident' and concept_signal < 1.0:
        centrality -= 0.1
    return max(0.0, min(round(centrality, 3), 1.0)), matched_topics, concept_alignment, secondary_alignment


def _candidate_from_doc(
    query: HadithTopicalQuery,
    doc: GuidanceUnitDocument,
    *,
    score: float,
    retrieval_origin: str,
    lexical_overlap_ratio: float = 0.0,
    semantic_score: float = 0.0,
) -> HadithTopicalCandidate:
    central_topic_score, matched_topics, concept_alignment, secondary_alignment = _central_topic_score(
        query,
        doc,
        lexical_overlap_ratio=lexical_overlap_ratio,
    )
    matched_terms = tuple(dict.fromkeys((*matched_topics, *((doc.metadata or {}).get('matched_terms') or ()))))
    incidental_penalty = max(0.0, min(float(doc.narrative_penalty or 0.0), 1.0))
    metadata = {
        'guidance_unit_id': doc.guidance_unit_id,
        'span_text': doc.span_text,
        'snippet': doc.span_text,
        'english_text': doc.span_text,
        'contextual_summary': doc.summary_text or doc.span_text,
        'central_concept_ids': list(doc.central_concept_ids),
        'secondary_concept_ids': list(doc.secondary_concept_ids),
        'directness_score': doc.directness_score,
        'answerability_score': doc.answerability_score,
        'narrative_penalty': doc.narrative_penalty,
        'concept_alignment_count': concept_alignment,
        'secondary_alignment_count': secondary_alignment,
        **dict(doc.metadata or {}),
    }
    return HadithTopicalCandidate(
        canonical_ref=doc.parent_hadith_ref,
        source_id=doc.collection_source_id,
        retrieval_origin=retrieval_origin,
        lexical_score=score,
        vector_score=round(semantic_score, 4),
        fusion_score=score,
        central_topic_score=central_topic_score,
        answerability_score=max(0.0, min(float(doc.answerability_score or 0.0), 1.0)),
        incidental_topic_penalty=incidental_penalty,
        guidance_role=_normalized_role(doc.guidance_role),
        topic_family=doc.topic_family,
        matched_topics=matched_topics,
        matched_terms=matched_terms,
        metadata=metadata,
    )


class HadithGuidanceUnitRetriever:
    """Retrieve guidance-unit candidates from a local artifact and/or OpenSearch."""

    def __init__(
        self,
        *,
        artifact_path: str | Path | None = None,
        opensearch_client: OpenSearchClient | None = None,
    ) -> None:
        self.artifact_path = Path(artifact_path) if artifact_path else self._resolve_default_artifact_path()
        self.opensearch_client = opensearch_client or OpenSearchClient.from_environment()

    @staticmethod
    def _resolve_default_artifact_path() -> Path | None:
        env = (os.getenv('DALIL_HADITH_GUIDANCE_UNITS_PATH') or '').strip()
        if env:
            return Path(env)
        for candidate in _DEFAULT_ARTIFACT_PATHS:
            if candidate.exists():
                return candidate
        return None

    @property
    def artifact_available(self) -> bool:
        return self.artifact_path is not None and self.artifact_path.exists()

    def retrieve(
        self,
        *,
        query: HadithTopicalQuery,
        collection_source_id: str | None = None,
        limit: int = 12,
    ) -> tuple[list[HadithTopicalCandidate], dict[str, Any]]:
        debug: dict[str, Any] = {
            'artifact_path': str(self.artifact_path) if self.artifact_path else None,
            'artifact_available': self.artifact_available,
            'opensearch_enabled': self.opensearch_client.is_enabled,
        }
        candidates: list[HadithTopicalCandidate] = []
        if self.artifact_available:
            artifact_candidates = self._retrieve_from_artifact(query, collection_source_id=collection_source_id, limit=max(8, limit * 2))
            candidates.extend(artifact_candidates)
            debug['artifact_candidate_count'] = len(artifact_candidates)
        else:
            debug['artifact_candidate_count'] = 0
        if self.opensearch_client.is_enabled:
            try:
                os_candidates = self._retrieve_from_opensearch(query, collection_source_id=collection_source_id, limit=max(8, limit * 2))
                candidates.extend(os_candidates)
                debug['opensearch_candidate_count'] = len(os_candidates)
            except Exception as exc:  # pragma: no cover - integration-only path
                debug['opensearch_error'] = str(exc)
                debug['opensearch_candidate_count'] = 0
        else:
            debug['opensearch_candidate_count'] = 0
        deduped: dict[tuple[str, str], HadithTopicalCandidate] = {}
        for candidate in candidates:
            key = (candidate.canonical_ref, str((candidate.metadata or {}).get('guidance_unit_id') or ''))
            existing = deduped.get(key)
            existing_score = float(existing.fusion_score or 0.0) if existing else -1.0
            candidate_score = float(candidate.fusion_score or 0.0)
            if existing is None or candidate_score > existing_score:
                deduped[key] = candidate
        best_per_parent: dict[str, HadithTopicalCandidate] = {}
        for candidate in deduped.values():
            existing = best_per_parent.get(candidate.canonical_ref)
            if existing is None:
                best_per_parent[candidate.canonical_ref] = candidate
                continue
            current = (
                float(candidate.fusion_score or 0.0),
                float(candidate.central_topic_score or 0.0),
                float(candidate.answerability_score or 0.0),
                -float(candidate.incidental_topic_penalty or 0.0),
            )
            previous = (
                float(existing.fusion_score or 0.0),
                float(existing.central_topic_score or 0.0),
                float(existing.answerability_score or 0.0),
                -float(existing.incidental_topic_penalty or 0.0),
            )
            if current > previous:
                best_per_parent[candidate.canonical_ref] = candidate
        ordered = sorted(
            best_per_parent.values(),
            key=lambda item: (
                -float(item.fusion_score or 0.0),
                -float(item.central_topic_score or 0.0),
                -float(item.answerability_score or 0.0),
                float(item.incidental_topic_penalty or 0.0),
                item.canonical_ref,
            ),
        )[: max(1, int(limit))]
        debug['candidate_count'] = len(ordered)
        debug['deduped_parent_count'] = len(best_per_parent)
        return ordered, debug

    def _retrieve_from_artifact(self, query: HadithTopicalQuery, *, collection_source_id: str | None, limit: int) -> list[HadithTopicalCandidate]:
        documents = self._load_artifact_documents(self.artifact_path)
        query_tokens = _tokens(query.normalized_query or query.raw_query)
        query_topics = set(query.topic_candidates or ())
        scored: list[tuple[float, float, GuidanceUnitDocument, float]] = []
        for doc in documents:
            if collection_source_id and doc.collection_source_id != collection_source_id:
                continue
            text_tokens = _tokens(doc.span_text)
            summary_tokens = _tokens(doc.summary_text)
            overlap_ratio = min(len(query_tokens & (text_tokens | summary_tokens)) / max(len(query_tokens), 1), 1.0)
            centrality, matched_topics, concept_alignment, secondary_alignment = _central_topic_score(
                query,
                doc,
                lexical_overlap_ratio=overlap_ratio,
            )
            answerability = max(0.0, min(float(doc.answerability_score or 0.0), 1.0))
            narrative_penalty = max(0.0, min(float(doc.narrative_penalty or 0.0), 1.0))
            builder_rank = max(0.0, min(float((doc.metadata or {}).get('builder_rank_score') or 0.0), 1.0))
            role_bonus = 0.12 if (query.query_profile == 'prophetic_guidance' and _normalized_role(doc.guidance_role) == 'direct_moral_instruction') else 0.0
            if query_topics and not (concept_alignment or secondary_alignment) and overlap_ratio < 0.34:
                continue
            semantic = score_text_against_query(
                query_text=query.normalized_query or query.raw_query,
                document_text=' '.join(filter(None, [doc.span_text, doc.summary_text or ''])),
                alias_terms=tuple(query.topic_candidates or ()),
            )
            fused_rank = fuse_lexical_and_semantic(lexical_score=overlap_ratio, semantic_score=semantic.semantic_score, semantic_weight=0.28)
            score = (
                0.28 * centrality
                + 0.12 * overlap_ratio
                + 0.18 * semantic.semantic_score
                + 0.12 * fused_rank
                + 0.16 * answerability
                + 0.14 * builder_rank
                + role_bonus
                - 0.18 * narrative_penalty
            )
            if _normalized_role(doc.guidance_role) == 'narrative_incident' and concept_alignment == 0 and semantic.semantic_score < 0.24 and score < 0.58:
                continue
            if score < 0.24:
                continue
            scored.append((round(score, 4), centrality, doc, overlap_ratio, semantic.semantic_score))
        scored.sort(key=lambda item: (-item[0], -item[1], -float(item[2].answerability_score or 0.0), item[2].guidance_unit_id))
        return [
            _candidate_from_doc(query, doc, score=score, retrieval_origin='guidance_artifact_hybrid' if semantic_score >= 0.22 else 'guidance_artifact', lexical_overlap_ratio=overlap_ratio, semantic_score=semantic_score)
            for score, _centrality, doc, overlap_ratio, semantic_score in scored[: max(1, int(limit))]
        ]

    def _retrieve_from_opensearch(self, query: HadithTopicalQuery, *, collection_source_id: str | None, limit: int) -> list[HadithTopicalCandidate]:
        body = build_hadith_guidance_bm25_query(query, collection_source_id=collection_source_id, size=max(8, int(limit)))
        response = self.opensearch_client.search(index=HADITH_GUIDANCE_UNIT_INDEX, body=body)
        hits = (((response or {}).get('hits') or {}).get('hits') or [])
        candidates: list[HadithTopicalCandidate] = []
        for hit in hits:
            source = hit.get('_source') or {}
            guidance_unit_id = str(source.get('guidance_unit_id') or '').strip()
            parent_ref = str(source.get('parent_hadith_ref') or '').strip()
            collection_source_id_value = str(source.get('collection_source_id') or '').strip()
            if not guidance_unit_id or not parent_ref or not collection_source_id_value:
                continue
            doc = GuidanceUnitDocument(
                guidance_unit_id=guidance_unit_id,
                parent_hadith_ref=parent_ref,
                collection_source_id=collection_source_id_value,
                span_text=str(source.get('span_text') or ''),
                summary_text=str(source.get('summary_text') or '') or None,
                guidance_role=_normalized_role(str(source.get('guidance_role') or 'narrative_incident')),
                topic_family=str(source.get('topic_family') or '') or None,
                central_concept_ids=tuple(source.get('central_concept_ids') or ()),
                secondary_concept_ids=tuple(source.get('secondary_concept_ids') or ()),
                directness_score=float(source.get('directness_score') or 0.0),
                answerability_score=float(source.get('answerability_score') or 0.0),
                narrative_penalty=float(source.get('narrative_penalty') or 0.0),
                span_start=source.get('span_start'),
                span_end=source.get('span_end'),
                numbering_quality=str(source.get('numbering_quality') or '') or None,
                metadata=dict(source.get('metadata') or {}),
            )
            score = float(hit.get('_score') or 0.0)
            candidates.append(_candidate_from_doc(query, doc, score=score, retrieval_origin='guidance_opensearch'))
        return candidates[: max(1, int(limit))]

    @staticmethod
    @lru_cache(maxsize=4)
    def _load_artifact_documents(path: Path | None) -> tuple[GuidanceUnitDocument, ...]:
        if path is None or not path.exists():
            return ()
        documents: list[GuidanceUnitDocument] = []
        with path.open('r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                documents.append(
                    GuidanceUnitDocument(
                        guidance_unit_id=str(payload['guidance_unit_id']),
                        parent_hadith_ref=str(payload['parent_hadith_ref']),
                        collection_source_id=str(payload['collection_source_id']),
                        span_text=str(payload['span_text']),
                        summary_text=str(payload.get('summary_text') or '') or None,
                        guidance_role=_normalized_role(str(payload.get('guidance_role') or 'narrative_incident')),
                        topic_family=str(payload.get('topic_family') or '') or None,
                        central_concept_ids=tuple(payload.get('central_concept_ids') or ()),
                        secondary_concept_ids=tuple(payload.get('secondary_concept_ids') or ()),
                        directness_score=float(payload.get('directness_score') or 0.0),
                        answerability_score=float(payload.get('answerability_score') or 0.0),
                        narrative_penalty=float(payload.get('narrative_penalty') or 0.0),
                        span_start=payload.get('span_start'),
                        span_end=payload.get('span_end'),
                        numbering_quality=str(payload.get('numbering_quality') or '') or None,
                        metadata=dict(payload.get('metadata') or {}),
                    )
                )
        return tuple(documents)
