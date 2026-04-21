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
from infrastructure.search.index_names import HADITH_BUKHARI_TOPICAL_INDEX, HADITH_TOPICAL_INDEX
from infrastructure.search.opensearch.hadith_bukhari_queries import (
    build_bukhari_bm25_query,
    build_bukhari_knn_query,
    normalise_family,
)
from infrastructure.search.opensearch.hadith_topical_queries import build_hadith_topical_bm25_query
from infrastructure.search.opensearch_client import OpenSearchClient


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BUKHARI_SOURCE_ID = 'hadith:bukhari'

# RRF constant k=60 is the standard choice (Robertson et al.)
# Score for rank-1 in a single list: 1/61 ≈ 0.0164
# Score for rank-1 in both lists:    2/61 ≈ 0.0328
# Used to normalise rrf_score → [0, 1] for proxy score derivation
_RRF_K = 60
_RRF_MAX_SINGLE_LIST = 1.0 / (_RRF_K + 1)
_RRF_MAX_DUAL_LIST = 2.0 / (_RRF_K + 1)


# ---------------------------------------------------------------------------
# Bukhari collection detection
# ---------------------------------------------------------------------------

def _is_bukhari_collection(collection_source_id: str | None) -> bool:
    """Return True when the request targets the Sahih al-Bukhari corpus."""
    return bool(collection_source_id and 'bukhari' in str(collection_source_id).lower())


# ---------------------------------------------------------------------------
# Embedding — lazy import, graceful fallback
# ---------------------------------------------------------------------------

def _get_query_embedding(text: str) -> list[float] | None:
    """Attempt to obtain a dense embedding for query text.

    Tries known DALIL embedding infrastructure import paths.  Returns None if
    the embedding layer is unavailable or errors — kNN retrieval is then
    silently skipped and BM25 results are used alone.
    """
    try:
        from infrastructure.embeddings.client import embed_text  # type: ignore[import]
        result = embed_text(text)
        return list(result) if result else None
    except Exception:
        pass
    try:
        from infrastructure.embeddings import get_embedding  # type: ignore[import]
        result = get_embedding(text)
        return list(result) if result else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def _rrf_combine(
    *ranked_hit_lists: list[dict[str, Any]],
    k: int = _RRF_K,
    id_field: str = 'hadith_id',
) -> list[tuple[float, dict[str, Any]]]:
    """Combine ranked OpenSearch hit lists via Reciprocal Rank Fusion.

    Standard RRF formula:  score(d) = Σ 1 / (k + rank(d, list_i))
    where rank is 1-indexed and summation is over all lists that contain d.

    Args:
        *ranked_hit_lists:  Each list is a sequence of OpenSearch hit dicts
                            (the elements of response['hits']['hits']).
        k:                  RRF constant (default 60, standard choice).
        id_field:           Field in _source used as the document identity key.

    Returns:
        List of (rrf_score, hit) tuples, sorted by rrf_score descending.
        The winning hit for each document ID is the one from whichever list
        has that document; BM25 hit takes precedence over kNN hit so that
        the richer _source payload (excluding the embedding vector) is kept.
    """
    scores: dict[str, float] = {}
    # Prefer the hit from the first list (BM25) for each doc_id so that the
    # full _source is retained from the richer payload.
    primary_hits: dict[str, dict[str, Any]] = {}

    for ranked_list in ranked_hit_lists:
        for rank, hit in enumerate(ranked_list, start=1):
            source = hit.get('_source') or {}
            doc_id = str(source.get(id_field) or '').strip()
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
            if doc_id not in primary_hits:
                primary_hits[doc_id] = hit

    return sorted(
        [(scores[doc_id], primary_hits[doc_id]) for doc_id in scores],
        key=lambda pair: pair[0],
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Candidate construction — existing enriched OpenSearch index
# ---------------------------------------------------------------------------

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


def _candidate_from_opensearch_source(
    query_topics: tuple[str, ...],
    source: dict[str, Any],
    *,
    score: float,
    retrieval_origin: str,
) -> HadithTopicalCandidate:
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


# ---------------------------------------------------------------------------
# Candidate construction — new Bukhari hybrid index
# ---------------------------------------------------------------------------

def _derive_guidance_role_from_bukhari(
    *,
    is_prophetic: bool,
    synthetic_baab_label: str,
) -> str:
    """Derive a guidance_role value from Bukhari fields.

    For direct prophetic statements we use 'direct_moral_instruction' — the
    strongest signal for the reranker and selector.  For other records we infer
    from the chapter label rather than leaving it as a flat 'narrative_incident'.
    """
    if is_prophetic:
        return 'direct_moral_instruction'
    label_lower = synthetic_baab_label.lower()
    if any(kw in label_lower for kw in ('warning', 'forbidden', 'prohibit', 'punishment', 'forbade')):
        return 'warning'
    if any(kw in label_lower for kw in ('virtue', 'excellence', 'merit', 'reward', 'best', 'good manners')):
        return 'virtue_statement'
    return 'narrative_incident'


def _derive_matched_topics_from_bukhari(
    query_topics: tuple[str, ...],
    *,
    matn_text: str,
    synthetic_baab_label: str,
    kitab_title_english: str,
    kitab_domain: list[str],
    source_query_family: str | None,
    dalil_family: str | None,
) -> tuple[str, ...]:
    """Derive matched_topics for a Bukhari candidate.

    Since the Bukhari index does not carry enriched topic_tags, we match
    topic_candidates against the available textual signals in priority order:

    1. Substring match in synthetic_baab_label + matn_text + kitab_title
    2. kitab_domain alignment (raw domain strings from the source record)
    3. Family-level alignment when source and query share the same family
       (coarse but prevents false abstentions for eschatology queries)
    """
    if not query_topics:
        return ()

    search_text = ' '.join(
        part for part in (matn_text, synthetic_baab_label, kitab_title_english) if part
    ).lower()

    # Pass 1 — literal substring match
    matched: list[str] = [
        topic for topic in query_topics
        if str(topic).strip().lower() in search_text
    ]
    if matched:
        return tuple(dict.fromkeys(matched))

    # Pass 2 — kitab_domain alignment
    domain_set = {str(d).strip().lower() for d in kitab_domain if d}
    domain_matched: list[str] = [
        topic for topic in query_topics
        if str(topic).strip().lower() in domain_set
        or any(str(topic).strip().lower() in d for d in domain_set)
    ]
    if domain_matched:
        return tuple(dict.fromkeys(domain_matched))

    # Pass 3 — family-level alignment
    # When the source document belongs to the same Bukhari query_family that
    # DALIL resolved for the current query, treat the top topic_candidate as
    # matched.  This prevents perfectly valid eschatology / ritual / aqeedah
    # hits from being rejected solely because their matn does not literally
    # contain the query term.
    if source_query_family and dalil_family and query_topics:
        resolved_bukhari_family = normalise_family(dalil_family)
        if resolved_bukhari_family and resolved_bukhari_family == source_query_family:
            return (query_topics[0],)

    return ()


def _derive_proxy_scores_from_bukhari(
    *,
    is_prophetic: bool,
    rrf_score: float,
    has_matched_topics: bool,
) -> tuple[float, float, float]:
    """Derive (central_topic_score, answerability_score, narrative_specificity_score).

    These proxy scores must satisfy the result_selector thresholds so that
    legitimate Bukhari hits are not silently dropped:
        minimum_centrality:    0.42 (general), up to 0.48 (ritual)
        minimum_answerability: 0.48 (general), up to 0.58 (prophetic_guidance)

    The RRF score is normalised against _RRF_MAX_DUAL_LIST (the maximum
    achievable score when a document appears at rank-1 in both the BM25 and
    kNN lists).  Even a BM25-only result at rank-1 achieves ~0.50 of max.

    Design intent:
        - Direct prophetic statements pass answerability comfortably (0.72)
        - Non-prophetic hadith pass the general threshold (0.52) but will
          score lower in the selector's composite and be ranked below direct
          prophetic statements from the same RRF tier
        - Topic alignment bonus prevents centrality from being too flat
    """
    rrf_normalised = min(rrf_score / _RRF_MAX_DUAL_LIST, 1.0)
    topic_bonus = 0.10 if has_matched_topics else 0.0

    # Central topic score: RRF signal + topic alignment bonus, floored at 0.44
    central_topic_score = round(
        min(0.44 + rrf_normalised * 0.40 + topic_bonus, 0.95),
        4,
    )

    if is_prophetic:
        answerability_score = 0.72
        narrative_specificity_score = 0.08
    else:
        answerability_score = 0.52
        narrative_specificity_score = 0.35

    return central_topic_score, answerability_score, narrative_specificity_score


def _candidate_from_bukhari_hit(
    query_topics: tuple[str, ...],
    rrf_score: float,
    source: dict[str, Any],
    *,
    retrieval_origin: str,
    dalil_family: str | None = None,
) -> HadithTopicalCandidate | None:
    """Map a Bukhari OpenSearch hit source to a HadithTopicalCandidate.

    Returns None for stub records that escaped index-level filtering (safety
    guard; should be a no-op in production since the query already filters
    is_stub = false).
    """
    # Guard: never surface stub records regardless of index state
    if source.get('is_stub'):
        return None

    hadith_id = str(source.get('hadith_id') or '').strip()
    if not hadith_id:
        return None

    matn_text = str(source.get('matn_text') or '').strip()
    synthetic_baab_label = str(source.get('synthetic_baab_label') or '').strip()
    kitab_title_english = str(source.get('kitab_title_english') or '').strip()
    narrator = str(source.get('narrator') or '').strip() or None
    is_prophetic = bool(source.get('has_direct_prophetic_statement'))
    source_query_family = str(source.get('query_family') or '').strip() or None
    kitab_domain = [str(d) for d in (source.get('kitab_domain') or []) if d]
    in_book_reference = str(source.get('in_book_reference') or '').strip() or None
    reference_url = str(source.get('reference_url') or '').strip() or None

    guidance_role = _derive_guidance_role_from_bukhari(
        is_prophetic=is_prophetic,
        synthetic_baab_label=synthetic_baab_label,
    )

    matched_topics = _derive_matched_topics_from_bukhari(
        query_topics,
        matn_text=matn_text,
        synthetic_baab_label=synthetic_baab_label,
        kitab_title_english=kitab_title_english,
        kitab_domain=kitab_domain,
        source_query_family=source_query_family,
        dalil_family=dalil_family,
    )

    central_topic_score, answerability_score, narrative_specificity_score = (
        _derive_proxy_scores_from_bukhari(
            is_prophetic=is_prophetic,
            rrf_score=rrf_score,
            has_matched_topics=bool(matched_topics),
        )
    )

    # For eschatology passages the selector checks metadata['thematic_passage'].
    # Bukhari kitab 92 (Afflictions and the End of the World) records retrieved
    # for an eschatology query are functionally thematic passages for that topic.
    is_thematic_passage = bool(
        source_query_family == 'eschatology'
        and normalise_family(dalil_family) == 'eschatology'
    )

    return HadithTopicalCandidate(
        canonical_ref=hadith_id,
        source_id=_BUKHARI_SOURCE_ID,
        retrieval_origin=retrieval_origin,
        lexical_score=rrf_score,
        vector_score=None,
        fusion_score=rrf_score,
        rerank_score=None,
        central_topic_score=central_topic_score,
        answerability_score=answerability_score,
        narrative_specificity_score=narrative_specificity_score,
        incidental_topic_penalty=0.0,
        guidance_role=guidance_role,
        topic_family=source_query_family,
        matched_topics=matched_topics,
        matched_terms=matched_topics,  # reranker refines via text overlap
        metadata={
            # Fields expected by the reranker (_heuristic_rerank_score)
            'chapter_title_en': synthetic_baab_label,
            'book_title_en': kitab_title_english,
            'english_text': matn_text,
            'english_narrator': narrator,
            'contextual_summary': matn_text,
            'snippet': matn_text[:400] if matn_text else None,
            # Bukhari-specific enrichment
            'synthetic_baab_label': synthetic_baab_label,
            'synthetic_baab_id': source.get('synthetic_baab_id'),
            'kitab_num': source.get('kitab_num'),
            'hadith_global_num': source.get('hadith_global_num'),
            'has_direct_prophetic_statement': is_prophetic,
            'reference_url': reference_url,
            'in_book_reference': in_book_reference,
            'kitab_domain': kitab_domain,
            'query_family': source_query_family,
            # Thematic passage flag for selector's entity_eschatology check
            'thematic_passage': is_thematic_passage,
            # Proxy score audit trail — useful for debugging acceptance failures
            'rrf_score': round(rrf_score, 6),
            'guidance_role': guidance_role,
            'topic_family': source_query_family,
            'answerability_score': answerability_score,
            'narrative_specificity_score': narrative_specificity_score,
            'central_topic_score': central_topic_score,
            # Empty collections — compatible with reranker / composition pipeline
            'topic_tags': [],
            'directive_labels': [],
            'normalized_topic_terms': [],
            'incidental_topic_flags': [],
            'moral_concepts': [],
        },
    )


# ---------------------------------------------------------------------------
# Candidate generator
# ---------------------------------------------------------------------------

class HadithTopicalCandidateGenerator:
    def __init__(
        self,
        *,
        database_url: str | None = None,
        opensearch_client: OpenSearchClient | None = None,
    ) -> None:
        self.database_url = database_url
        self.opensearch_client = opensearch_client or OpenSearchClient.from_environment()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

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
            'retrieval_path': 'unknown',
        }

        # -----------------------------------------------------------------
        # Bukhari hybrid path — replaces both lexical DB and old BM25 paths
        # -----------------------------------------------------------------
        if _is_bukhari_collection(request.collection_source_id) and self.opensearch_client.is_enabled:
            return self._generate_bukhari(request, warnings=warnings, debug=debug)

        # -----------------------------------------------------------------
        # Existing enriched-index path (all other collections)
        # -----------------------------------------------------------------
        debug['retrieval_path'] = 'enriched_index'

        if lexical_hits is None:
            lexical_hits = self._load_lexical_hits(request)
            debug['lexical_hits_source'] = 'runtime_lookup'
        else:
            debug['lexical_hits_source'] = 'prefetched_shadow_baseline'

        lexical_candidates = tuple(
            candidate_from_lexical_hit(request.query.topic_candidates, hit)
            for hit in lexical_hits
        )
        candidates = list(lexical_candidates)
        debug['lexical_candidate_count'] = len(lexical_candidates)

        opensearch_candidates: tuple[HadithTopicalCandidate, ...] = ()
        if request.allow_opensearch and self.opensearch_client.is_enabled:
            try:
                opensearch_candidates = self._load_opensearch_candidates(request)
                candidates.extend(opensearch_candidates)
                debug['opensearch_candidate_count'] = len(opensearch_candidates)
            except Exception as exc:  # pragma: no cover
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
        return HadithTopicalCandidateGenerationResult(
            candidates=selected,
            warnings=tuple(dict.fromkeys(warnings)),
            debug=debug,
        )

    # ------------------------------------------------------------------
    # Bukhari hybrid retrieval
    # ------------------------------------------------------------------

    def _generate_bukhari(
        self,
        request: HadithTopicalCandidateGenerationRequest,
        *,
        warnings: list[str],
        debug: dict[str, Any],
    ) -> HadithTopicalCandidateGenerationResult:
        """Run BM25 + optional kNN on the Bukhari index and combine via RRF."""
        debug['retrieval_path'] = 'bukhari_hybrid'
        query = request.query
        dalil_family = query.topic_family
        normalized_query = query.normalized_query or query.raw_query
        search_size = max(20, int(request.candidate_limit) * 3)

        bm25_hits: list[dict[str, Any]] = []
        knn_hits: list[dict[str, Any]] = []
        knn_available = False

        # BM25 — always attempted
        try:
            bm25_body = build_bukhari_bm25_query(
                normalized_query=normalized_query,
                topic_candidates=query.topic_candidates,
                dalil_family=dalil_family,
                size=search_size,
            )
            bm25_response = self.opensearch_client.search(
                index=HADITH_BUKHARI_TOPICAL_INDEX,
                body=bm25_body,
            )
            bm25_hits = (((bm25_response or {}).get('hits') or {}).get('hits') or [])
            debug['bm25_hit_count'] = len(bm25_hits)
        except Exception as exc:
            warnings.append('bukhari_bm25_unavailable')
            debug['bm25_error'] = str(exc)

        # kNN — attempted only when embedding is available
        query_vector = _get_query_embedding(normalized_query)
        if query_vector:
            knn_available = True
            try:
                knn_body = build_bukhari_knn_query(
                    query_vector=query_vector,
                    dalil_family=dalil_family,
                    k=20,
                )
                knn_response = self.opensearch_client.search(
                    index=HADITH_BUKHARI_TOPICAL_INDEX,
                    body=knn_body,
                )
                knn_hits = (((knn_response or {}).get('hits') or {}).get('hits') or [])
                debug['knn_hit_count'] = len(knn_hits)
            except Exception as exc:
                warnings.append('bukhari_knn_unavailable')
                debug['knn_error'] = str(exc)
        else:
            debug['knn_hit_count'] = 0
            debug['knn_skipped'] = 'embedding_unavailable'

        debug['knn_enabled'] = knn_available
        debug['retrieval_origin'] = 'bukhari_hybrid_bm25_knn' if knn_available and knn_hits else 'bukhari_hybrid_bm25'

        if not bm25_hits and not knn_hits:
            warnings.append('bukhari_hybrid_no_hits')
            return HadithTopicalCandidateGenerationResult(
                candidates=(),
                warnings=tuple(dict.fromkeys(warnings)),
                debug=debug,
            )

        # RRF combination
        combined = _rrf_combine(bm25_hits, knn_hits, k=_RRF_K)
        debug['rrf_combined_count'] = len(combined)

        # Apply prophetic statement boost BEFORE candidate construction so the
        # boost is reflected in the rrf_score stored on the candidate (and
        # visible in debug / audit logs).
        #
        # Boost: ×1.3 for direct prophetic statements in akhlaq, foundational,
        # aqeedah families — per the retrieval spec.
        _PROPHETIC_BOOST_FAMILIES = frozenset({'akhlaq', 'foundational', 'aqeedah'})
        bukhari_family_for_boost = (
            dalil_family.lower() if dalil_family else None
        )
        apply_prophetic_boost = bool(
            bukhari_family_for_boost
            and (
                bukhari_family_for_boost in _PROPHETIC_BOOST_FAMILIES
                or any(
                    fam in _PROPHETIC_BOOST_FAMILIES
                    for fam in (bukhari_family_for_boost,)
                )
            )
        )

        retrieval_origin = debug['retrieval_origin']
        candidates: list[HadithTopicalCandidate] = []
        for rrf_score, hit in combined:
            source = hit.get('_source') or {}

            # Apply prophetic boost to rrf_score when eligible
            effective_rrf_score = rrf_score
            if apply_prophetic_boost and source.get('has_direct_prophetic_statement'):
                effective_rrf_score = rrf_score * 1.3

            candidate = _candidate_from_bukhari_hit(
                query.topic_candidates,
                effective_rrf_score,
                source,
                retrieval_origin=retrieval_origin,
                dalil_family=dalil_family,
            )
            if candidate is not None:
                candidates.append(candidate)

        # Sort by effective RRF score (already encoded in fusion_score)
        candidates.sort(
            key=lambda c: (
                -float(c.fusion_score or 0.0),
                -float(c.answerability_score or 0.0),
                -float(c.central_topic_score or 0.0),
                c.canonical_ref,
            ),
        )
        selected = tuple(candidates[: max(1, int(request.candidate_limit))])
        debug['candidate_count'] = len(selected)
        debug['candidate_origins'] = [c.retrieval_origin for c in selected]
        debug['top_refs'] = [c.canonical_ref for c in selected[:5]]

        return HadithTopicalCandidateGenerationResult(
            candidates=selected,
            warnings=tuple(dict.fromkeys(warnings)),
            debug=debug,
        )

    # ------------------------------------------------------------------
    # Existing helpers (unchanged)
    # ------------------------------------------------------------------

    def _load_lexical_hits(self, request: HadithTopicalCandidateGenerationRequest) -> list[HadithLexicalHit]:
        service = HadithService(database_url=self.database_url)
        return service.search_topically(
            query_text=request.query.normalized_query or request.query.raw_query,
            collection_source_id=request.collection_source_id,
            limit=max(1, int(request.lexical_limit)),
        )

    def _load_opensearch_candidates(
        self,
        request: HadithTopicalCandidateGenerationRequest,
    ) -> tuple[HadithTopicalCandidate, ...]:
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
