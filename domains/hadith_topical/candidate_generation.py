"""Topical hadith candidate generation — Bukhari hybrid + legacy enriched-index paths.

Retrieval architecture:
    Bukhari queries  →  BM25 + kNN on hadith_topical_bukhari, fused via RRF
    All other collections  →  Lexical DB + optional enriched OpenSearch index

Key design principles:
    - RRF normalised against _RRF_MAX_DUAL_LIST: forces lexical + semantic
      agreement for maximum scores; prevents pure-kNN hallucinations from
      clearing the evidence gate on their own.
    - Lexical anchor penalty: candidates with no textual match to the query
      (pure vector guesses) receive a -0.20 central_topic_score penalty,
      ensuring they fail the selector's minimum_centrality threshold rather
      than producing hallucinated answers.
    - Narrator field is never searched: prevents narrator-name substring
      collisions (e.g. "Abu Az-Zinad" matching a "zina" query).
    - Citation fields (reference_url, in_book_reference, kitab_domain) are
      always propagated through metadata so the renderer can produce correct
      source attribution.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import re

from domains.hadith.contracts import HadithLexicalHit
from domains.hadith.service import HadithService
from domains.hadith_topical.contracts import (
    HadithTopicalCandidate,
    HadithTopicalCandidateGenerationRequest,
    HadithTopicalCandidateGenerationResult,
)
from domains.hadith_topical.enricher import build_enriched_document
from domains.hadith_topical.query_topic_resolver import TopicResolution, resolve_topic
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
# Score for rank-1 in a single list:  1/(60+1) ≈ 0.0164
# Score for rank-1 in both lists:     2/(60+1) ≈ 0.0328
# Normalising against DUAL_LIST maps [0, 0.0328] → [0, 1.0].
# A BM25-only rank-1 hit achieves ≈0.50 of max; appearing in both at rank-1
# achieves 1.00.  This penalises pure-kNN hallucinations automatically.
_RRF_K = 60
_RRF_MAX_SINGLE_LIST = 1.0 / (_RRF_K + 1)   # kept for documentation / future use
_RRF_MAX_DUAL_LIST   = 2.0 / (_RRF_K + 1)

# Families eligible for the 1.3× prophetic-statement boost.
# Eschatology is included: direct prophetic statements such as
# "The Hour will not come until…" are primary evidence for that family.
_PROPHETIC_BOOST_FAMILIES: frozenset[str] = frozenset({
    'akhlaq',
    'foundational',
    'aqeedah',
    'eschatology',
})


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

    Standard RRF formula:  score(d) = Σ  1 / (k + rank(d, list_i))
    where rank is 1-indexed and summation is over all lists that contain d.

    Args:
        *ranked_hit_lists:  Each list is a sequence of OpenSearch hit dicts
                            (the elements of response['hits']['hits']).
        k:                  RRF constant (default 60, standard choice).
        id_field:           Field in _source used as the document identity key.

    Returns:
        List of (rrf_score, hit) tuples, sorted by rrf_score descending.
        BM25 hit takes precedence over kNN hit for each document ID so that
        the richer _source payload is retained from the lexical lane.
    """
    scores: dict[str, float] = {}
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
# Candidate construction — existing enriched OpenSearch index (legacy path)
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
    matched_topics = tuple(
        topic for topic in query_topics
        if topic in set(enriched.topic_tags) | set(enriched.normalized_topic_terms)
    )
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
    matched_topics = tuple(
        topic for topic in query_topics
        if topic in set(topic_tags) | set(normalized_topic_terms)
    )
    matched_terms = tuple(dict.fromkeys(
        tuple(source.get('normalized_alias_terms') or ()) + tuple(matched_topics)
    ))
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
# Candidate construction — Bukhari hybrid index
# ---------------------------------------------------------------------------

def _derive_guidance_role_from_bukhari(
    *,
    is_prophetic: bool,
    synthetic_baab_label: str,
) -> str:
    """Derive a guidance_role value from Bukhari index fields.

    Direct prophetic statements use 'direct_moral_instruction' — the strongest
    signal for the reranker and selector.  Non-prophetic records are classified
    from the chapter label rather than left as a flat 'narrative_incident'.
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

    Matching passes in priority order:

    1. Literal substring match in (matn_text + synthetic_baab_label + kitab_title).
       Most precise — the query concept is directly present in the text.

    2. kitab_domain alignment.
       A topic_candidate that matches a domain tag on the record (e.g. 'akhlaq',
       'eschatology') counts as a domain-level match.

    3. Family-level alignment.
       When the record's query_family matches DALIL's resolved family for the
       current query, the top topic_candidate is treated as matched.  This
       prevents valid eschatology / ritual / aqeedah hits from being rejected
       solely because their matn does not literally repeat the query keyword
       (e.g. "Dajjal" queries against hadiths describing his traits).
    """
    if not query_topics:
        return ()

    search_text = ' '.join(
        part for part in (matn_text, synthetic_baab_label, kitab_title_english) if part
    ).lower()

    # Pass 1 — literal substring
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
    hit_family: str | None = None,
) -> tuple[float, float, float]:
    """Derive (central_topic_score, answerability_score, narrative_specificity_score).

    Normalisation:
        RRF score is normalised against _RRF_MAX_DUAL_LIST (≈0.0328).
        A document at rank-1 in BM25 only achieves ≈0.50 of normalised max.
        A document at rank-1 in both BM25 and kNN achieves 1.00.
        This design ensures pure-kNN hallucinations never reach the highest
        proxy scores because they cannot contribute a BM25 rank.

    Lexical anchor penalty (-0.20):
        Applied when has_matched_topics is False — the retrieved hadith has no
        textual or domain alignment with the query (pure vector guess).
        The penalty drops central_topic_score below the selector's
        minimum_centrality threshold (0.42), causing a safe abstain rather
        than a hallucinated answer.

    Family-specific floors:
        eschatology: 0.58  (higher gate threshold for that family)
        all others:  0.44  (general floor, well above minimum_centrality 0.42)

    Selector thresholds this must satisfy:
        minimum_centrality:    0.42 (general), 0.48 (ritual), 0.58 (eschatology)
        minimum_answerability: 0.48 (general), 0.58 (prophetic_guidance)
    """
    rrf_normalised = min(rrf_score / _RRF_MAX_DUAL_LIST, 1.0)
    topic_bonus    = 0.12 if has_matched_topics else 0.0
    # Lexical anchor penalty: pure kNN guesses with no textual grounding.
    # Floored at 0.0 — negative scores must not reach the selector.
    lexical_penalty = 0.0 if has_matched_topics else -0.20

    family_floor = 0.58 if hit_family == 'eschatology' else 0.44

    central_topic_score = round(
        min(max(family_floor + rrf_normalised * 0.38 + topic_bonus + lexical_penalty, 0.0), 0.95),
        4,
    )

    if is_prophetic:
        answerability_score          = 0.72
        narrative_specificity_score  = 0.08
    else:
        # Eschatology: non-prophetic narrations describing end-times entities /
        # events need a higher answerability floor so they pass the eschatology gate.
        answerability_score          = 0.70 if hit_family == 'eschatology' else 0.52
        narrative_specificity_score  = 0.35

    return central_topic_score, answerability_score, narrative_specificity_score


# ---------------------------------------------------------------------------
# Word-boundary anchor gate (v2) — the core runtime fix for narrator collisions
# ---------------------------------------------------------------------------

_WORD_BOUNDARY_CACHE: dict[str, re.Pattern[str]] = {}


def _word_boundary_pattern(token: str) -> re.Pattern[str]:
    """Cache word-boundary regex compilation per token."""
    pat = _WORD_BOUNDARY_CACHE.get(token)
    if pat is None:
        pat = re.compile(rf'\b{re.escape(token)}\b', re.IGNORECASE)
        _WORD_BOUNDARY_CACHE[token] = pat
    return pat


def _has_word_boundary_anchor(
    query_tokens: tuple[str, ...],
    source: dict[str, Any],
) -> bool:
    """Return True iff any query token word-boundary-matches the hit's searchable text.

    This is the hard gate that kills the zina/Abu-Az-Zinad collision at runtime.
    A record can only count as a genuine match if at least one query token
    literally appears (bounded) in:
        - matn_text_clean            (narrator-stripped body)
        - concept_vocabulary entries (per-record corpus phrases)
        - synthetic_baab_label       (chapter heading)

    The `narrator` field is intentionally NOT checked. Same rule at data,
    index, and runtime layers.

    When `query_tokens` is empty (degenerate query after stripping), the gate
    defers to BM25/kNN — a record passes because the retrieval layer had
    reason to surface it.
    """
    if not query_tokens:
        return True

    parts: list[str] = []
    matn_clean = source.get('matn_text_clean')
    if matn_clean:
        parts.append(str(matn_clean))
    vocab = source.get('concept_vocabulary') or ()
    if vocab:
        parts.append(' '.join(str(v) for v in vocab))
    baab = source.get('synthetic_baab_label')
    if baab:
        parts.append(str(baab))

    if not parts:
        return False

    full_text = ' '.join(parts)
    for token in query_tokens:
        if _word_boundary_pattern(token).search(full_text):
            return True
    return False


# ---------------------------------------------------------------------------
# v2 candidate construction — uses topical fields straight from the index
# ---------------------------------------------------------------------------

def _candidate_from_bukhari_v2_hit(
    *,
    resolution: TopicResolution,
    rrf_score: float,
    source: dict[str, Any],
    retrieval_origin: str,
    has_anchor: bool,
    dalil_family: str | None,
) -> HadithTopicalCandidate | None:
    """Map a Bukhari v2 index hit to a HadithTopicalCandidate.

    Replaces the heuristic `_derive_proxy_scores_from_bukhari` with direct
    use of index-side fields:
        - `topic_density`    → central_topic_score (unless anchor gate failed)
        - `primary_topics`   → matched_topics
        - `concept_vocabulary` → matched_terms (the phrases users can search for)

    When the anchor gate failed, the candidate carries central_topic_score=0.0
    and incidental_topic_penalty=1.0, ensuring the selector threshold will
    reject the record before it reaches the renderer. This is the
    belt-and-suspenders fix for vector hallucinations — even if BM25 and kNN
    both rank a record highly, it must survive the textual anchor check.
    """
    if source.get('is_stub'):
        return None

    hadith_id = str(source.get('hadith_id') or '').strip()
    if not hadith_id:
        return None

    matn_text_clean       = str(source.get('matn_text_clean') or '').strip()
    synthetic_baab_label  = str(source.get('synthetic_baab_label') or '').strip()
    kitab_title_english   = str(source.get('kitab_title_english') or '').strip()
    narrator              = str(source.get('narrator') or '').strip() or None
    is_prophetic          = bool(source.get('has_direct_prophetic_statement'))
    primary_topics        = tuple(str(x) for x in (source.get('primary_topics') or ()))
    secondary_topics      = tuple(str(x) for x in (source.get('secondary_topics') or ()))
    concept_vocab         = tuple(str(x) for x in (source.get('concept_vocabulary') or ()))
    topic_density         = float(source.get('topic_density') or 0.0)
    source_query_family   = str(source.get('query_family') or '').strip() or None
    kitab_domain          = [str(d) for d in (source.get('kitab_domain') or []) if d]
    in_book_reference     = str(source.get('in_book_reference') or '').strip() or None
    reference_url         = str(source.get('reference_url') or '').strip() or None

    # Central topic score — from index, gated by word-boundary anchor.
    central_topic_score = topic_density if has_anchor else 0.0

    # Answerability depends on prophetic signal + anchor + primary-topic match.
    # v2 candidates that passed the primary_topic hard filter have already
    # proven strong topical alignment — baseline higher than legacy v1.
    primary_matches_resolution = bool(
        resolution.primary_topic and resolution.primary_topic in primary_topics
    )
    if has_anchor and primary_matches_resolution:
        # Candidate is in the resolver's target topic — strongest signal class
        answerability_score = 0.90 if is_prophetic else 0.84
    elif is_prophetic and has_anchor:
        answerability_score = 0.80
    elif has_anchor:
        answerability_score = 0.70
    else:
        answerability_score = 0.25  # fails selector thresholds
    # Narrative specificity penalty: a well-targeted topical match on a
    # narrative record isn't "just narrative" — the LLM already judged it
    # central to the topic. Lower the penalty for primary-matched anchored
    # non-prophetic candidates so they clear the prophetic_guidance threshold.
    if primary_matches_resolution and has_anchor:
        narrative_specificity_score = 0.05 if is_prophetic else 0.15
    else:
        narrative_specificity_score = 0.10 if is_prophetic else 0.30

    # Hard penalty when no anchor — record becomes unselectable.
    incidental_topic_penalty = 0.0 if has_anchor else 1.0

    guidance_role = 'direct_moral_instruction' if is_prophetic else 'narrative_incident'

    # Matched topics / terms — directly from index.
    matched_topics = primary_topics
    matched_terms = concept_vocab

    metadata: dict[str, Any] = {
        # Fields consumed by reranker / composition (kept identical to v1 shape)
        'chapter_title_en':  synthetic_baab_label,
        'book_title_en':     kitab_title_english,
        'english_text':      matn_text_clean,
        'english_narrator':  narrator,
        'contextual_summary': matn_text_clean,
        'snippet':           matn_text_clean[:400] if matn_text_clean else None,

        # Bukhari-specific
        'synthetic_baab_label': synthetic_baab_label,
        'synthetic_baab_id':    source.get('synthetic_baab_id'),
        'kitab_num':            source.get('kitab_num'),
        'hadith_global_num':    source.get('hadith_global_num'),
        'has_direct_prophetic_statement': is_prophetic,

        # Citation
        'reference_url':     reference_url,
        'in_book_reference': in_book_reference,
        'kitab_domain':      kitab_domain,
        'query_family':      source_query_family,

        # Topical v2
        'primary_topics':    list(primary_topics),
        'secondary_topics':  list(secondary_topics),
        'concept_vocabulary': list(concept_vocab),
        'topic_density':     topic_density,

        # Audit trail
        'has_word_boundary_anchor': has_anchor,
        'rrf_score':          round(rrf_score, 6),
        'resolved_primary':   resolution.primary_topic,
        'resolved_family':    resolution.family,

        # builder_rank_score is read by the result_selector composite score
        # as an upstream pre-ranking signal (weight 0.08). v2 candidates that
        # passed the primary_topic hard filter AND carry the resolved primary
        # in their own topics have proven strong alignment upstream of the
        # selector — give them a high builder_rank so the selector's composite
        # clears threshold without requiring lexical/semantic score boosts
        # that can't be reliably produced for short queries.
        'builder_rank_score': (
            1.0 if (resolution.primary_topic and resolution.primary_topic in primary_topics)
            else (0.7 if any(s in primary_topics for s in resolution.confident_topics) else 0.3)
        ) if has_anchor else 0.0,

        # Empty compatibility collections (reranker expects these keys)
        'topic_tags':             [],
        'directive_labels':       [],
        'normalized_topic_terms': [],
        'incidental_topic_flags': [],
        'moral_concepts':         [],
    }

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
        incidental_topic_penalty=incidental_topic_penalty,
        guidance_role=guidance_role,
        topic_family=source_query_family,
        matched_topics=matched_topics,
        matched_terms=matched_terms,
        metadata=metadata,
    )


def _candidate_from_bukhari_hit(
    query_topics: tuple[str, ...],
    rrf_score: float,
    source: dict[str, Any],
    *,
    retrieval_origin: str,
    dalil_family: str | None = None,
) -> HadithTopicalCandidate | None:
    """Map a Bukhari OpenSearch hit _source to a HadithTopicalCandidate.

    Returns None for stub records that escaped index-level filtering (double
    guard; should be a no-op in production since the query already applies
    is_stub = false).
    """
    # Guard: never surface stub records regardless of index state
    if source.get('is_stub'):
        return None

    hadith_id = str(source.get('hadith_id') or '').strip()
    if not hadith_id:
        return None

    # Extract all fields explicitly so metadata is fully populated for the
    # renderer, reranker, and citation pipeline.
    matn_text            = str(source.get('matn_text') or '').strip()
    synthetic_baab_label = str(source.get('synthetic_baab_label') or '').strip()
    kitab_title_english  = str(source.get('kitab_title_english') or '').strip()
    narrator             = str(source.get('narrator') or '').strip() or None
    is_prophetic         = bool(source.get('has_direct_prophetic_statement'))
    source_query_family  = str(source.get('query_family') or '').strip() or None
    kitab_domain         = [str(d) for d in (source.get('kitab_domain') or []) if d]
    in_book_reference    = str(source.get('in_book_reference') or '').strip() or None
    reference_url        = str(source.get('reference_url') or '').strip() or None

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
            hit_family=source_query_family,
        )
    )

    # Eschatology passages: records from query_family='eschatology' retrieved
    # for an eschatology query are functionally thematic passages for the topic.
    # The selector checks metadata['thematic_passage'] for this family.
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
        matched_terms=matched_topics,   # reranker refines via text overlap
        metadata={
            # ── Fields expected by the reranker (_heuristic_rerank_score) ──
            'chapter_title_en':  synthetic_baab_label,
            'book_title_en':     kitab_title_english,
            'english_text':      matn_text,
            'english_narrator':  narrator,
            'contextual_summary': matn_text,
            'snippet':           matn_text[:400] if matn_text else None,
            # ── Bukhari-specific enrichment ──
            'synthetic_baab_label': synthetic_baab_label,
            'synthetic_baab_id':    source.get('synthetic_baab_id'),
            'kitab_num':            source.get('kitab_num'),
            'hadith_global_num':    source.get('hadith_global_num'),
            'has_direct_prophetic_statement': is_prophetic,
            # ── Citation fields — required by the renderer ──
            'reference_url':     reference_url,
            'in_book_reference': in_book_reference,
            'kitab_domain':      kitab_domain,
            'query_family':      source_query_family,
            # ── Selector flags ──
            'thematic_passage':  is_thematic_passage,
            # ── Proxy score audit trail (debug / acceptance failure diagnosis) ──
            'rrf_score':                    round(rrf_score, 6),
            'guidance_role':                guidance_role,
            'topic_family':                 source_query_family,
            'answerability_score':          answerability_score,
            'narrative_specificity_score':  narrative_specificity_score,
            'central_topic_score':          central_topic_score,
            # ── Empty collections — compatible with reranker / composition ──
            'topic_tags':              [],
            'directive_labels':        [],
            'normalized_topic_terms':  [],
            'incidental_topic_flags':  [],
            'moral_concepts':          [],
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
            'lexical_limit':   request.lexical_limit,
            'collection_source_id': request.collection_source_id,
            'topic_family':    request.query.topic_family,
            'directive_biases': list(request.query.directive_biases),
            'retrieval_path':  'unknown',
        }

        # -----------------------------------------------------------------
        # Bukhari hybrid path — replaces both lexical DB and legacy BM25
        # -----------------------------------------------------------------
        if _is_bukhari_collection(request.collection_source_id) and self.opensearch_client.is_enabled:
            return self._generate_bukhari(request, warnings=warnings, debug=debug)

        # -----------------------------------------------------------------
        # Legacy enriched-index path (all other collections)
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
        # Multi-factor sort: primary score, then answerability, centrality,
        # incidental penalty, narrative specificity, and stable ref tiebreak.
        deduped.sort(
            key=lambda item: (
                -float(item.fusion_score or item.lexical_score or 0.0),
                -float(item.answerability_score or 0.0),
                -float(item.central_topic_score or 0.0),
                 float(item.incidental_topic_penalty or 0.0),
                 float(item.narrative_specificity_score or 0.0),
                 item.canonical_ref,
            ),
        )
        selected = tuple(deduped[: max(1, int(request.candidate_limit))])
        debug['candidate_count']   = len(selected)
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
        """Run Bukhari v2 hybrid retrieval: resolver → BM25 + kNN → RRF → anchor gate.

        Flow:
            1. Resolve query to a taxonomy leaf (primary_topic) and
               secondary-boost candidates via deterministic vocabulary lookup.
            2. First attempt: run BM25 + kNN with strict primary_topic filter.
            3. Fallback: if the strict attempt returned nothing, relax the
               primary filter to family-only and retry. Prevents the common
               case where a broad query can't pin a single topic but should
               still surface something.
            4. RRF-fuse the two lanes.
            5. Apply the word-boundary anchor gate — records without any
               literal query-token match in matn_text_clean /
               concept_vocabulary / synthetic_baab_label get central_topic_score=0.0,
               which fails the selector threshold downstream. This is the
               hard fix for narrator collisions (zina vs "Abu Az-Zinad") and
               vector hallucinations.
            6. Apply the prophetic boost and emit candidates.
        """
        debug['retrieval_path'] = 'bukhari_hybrid_v2'
        query = request.query
        dalil_family = query.topic_family
        raw_query = query.raw_query or query.normalized_query or ''
        search_size = max(20, int(request.candidate_limit) * 3)

        # -- Step 1: resolver ---------------------------------------------
        # Resolver runs across ALL 182 taxonomy leafs rather than being
        # restricted by the upstream classifier's family hint. The
        # classifier's families (moral_guidance, entity_eschatology, etc.)
        # don't align 1:1 with taxonomy families — e.g. "intentions"
        # classifies as `moral_guidance` → `akhlaq`, but the right topic is
        # `foundational.intention_niyya`. The dalil_family hint is still
        # used at OpenSearch level as a fallback filter when no primary
        # topic is confidently resolved.
        resolution = resolve_topic(raw_query, query_family=None)
        debug['topic_resolution'] = resolution.as_debug()

        # Propagate resolved topics to the query so the downstream selector
        # (1) uses a calibrated threshold (the "no topic_candidates" path
        # defaults to 0.70 which is too strict for v2 candidates) and
        # (2) awards the matched_topics∩topic_candidates alignment bonus.
        # Merge any resolver output — even when no single primary was
        # confidently chosen (topically-broad queries), the secondary list
        # still gives the selector something to align against.
        any_resolution = bool(
            resolution.primary_topic
            or resolution.confident_topics
            or resolution.secondary_topics
        )
        if any_resolution:
            existing = tuple(query.topic_candidates or ())
            merged: list[str] = []
            seen: set[str] = set()
            for slug in (*existing, *resolution.confident_topics, *resolution.secondary_topics):
                if slug and slug not in seen:
                    seen.add(slug)
                    merged.append(slug)
            query.topic_candidates = tuple(merged)
            debug['query_topic_candidates_set'] = merged

        # -- Step 2: strict retrieval (primary_topic filter on) -----------
        bm25_hits, knn_hits, bm25_err, knn_err, knn_available = self._fetch_bukhari_hybrid(
            resolution=resolution,
            dalil_family=dalil_family,
            size=search_size,
            enforce_primary=True,
        )
        if bm25_err:
            warnings.append('bukhari_bm25_unavailable')
            debug['bm25_error'] = bm25_err
        if knn_err:
            warnings.append('bukhari_knn_unavailable')
            debug['knn_error'] = knn_err
        debug['strict_bm25_hits'] = len(bm25_hits)
        debug['strict_knn_hits']  = len(knn_hits)

        # -- Step 3: relaxed fallback -------------------------------------
        if not bm25_hits and not knn_hits and resolution.primary_topic:
            debug['strict_empty_fallback'] = True
            bm25_hits, knn_hits, _, _, knn_available = self._fetch_bukhari_hybrid(
                resolution=resolution,
                dalil_family=dalil_family,
                size=search_size,
                enforce_primary=False,
            )
            debug['relaxed_bm25_hits'] = len(bm25_hits)
            debug['relaxed_knn_hits']  = len(knn_hits)

        debug['knn_enabled'] = knn_available
        retrieval_origin = (
            'bukhari_v2_hybrid_bm25_knn' if knn_available and knn_hits
            else 'bukhari_v2_hybrid_bm25'
        )
        debug['retrieval_origin'] = retrieval_origin

        # -- Step 4: no-hits guard ----------------------------------------
        if not bm25_hits and not knn_hits:
            warnings.append('bukhari_hybrid_no_hits')
            return HadithTopicalCandidateGenerationResult(
                candidates=(),
                warnings=tuple(dict.fromkeys(warnings)),
                debug=debug,
            )

        # -- Step 5: RRF fuse + anchor gate + candidate build -------------
        combined = _rrf_combine(bm25_hits, knn_hits, k=_RRF_K)
        debug['rrf_combined_count'] = len(combined)

        # When the primary_topic hard filter was actually enforced AND produced
        # the results, every returned record has been certified by the LLM
        # enrichment to be about that topic. The anchor gate is redundant
        # there — and occasionally harmful (e.g. "antichrist" queries reach
        # Dajjal records whose matn uses "Dajjal" not "antichrist"). We only
        # apply the gate on the relaxed fallback path where the filter was
        # dropped and retrieval could surface non-topical hits.
        primary_filter_enforced = (
            resolution.primary_topic is not None
            and not debug.get('strict_empty_fallback', False)
        )
        debug['anchor_gate_applied'] = not primary_filter_enforced

        candidates: list[HadithTopicalCandidate] = []
        anchor_pass = 0
        anchor_fail = 0
        for rrf_score, hit in combined:
            source = hit.get('_source') or {}

            # Prophetic boost on RRF score (pre-candidate, so score trail is clean)
            effective_rrf = rrf_score
            family = (source.get('query_family') or '').lower()
            if source.get('has_direct_prophetic_statement') and family in _PROPHETIC_BOOST_FAMILIES:
                effective_rrf = rrf_score * 1.3

            if primary_filter_enforced:
                has_anchor = True  # trust the primary_topic filter
            else:
                has_anchor = _has_word_boundary_anchor(resolution.stripped_tokens, source)
            if has_anchor:
                anchor_pass += 1
            else:
                anchor_fail += 1

            candidate = _candidate_from_bukhari_v2_hit(
                resolution=resolution,
                rrf_score=effective_rrf,
                source=source,
                retrieval_origin=retrieval_origin,
                has_anchor=has_anchor,
                dalil_family=dalil_family,
            )
            if candidate is not None:
                candidates.append(candidate)

        debug['anchor_gate'] = {'pass': anchor_pass, 'fail': anchor_fail}

        candidates.sort(
            key=lambda c: (
                -float(c.fusion_score or 0.0),
                -float(c.central_topic_score or 0.0),
                -float(c.answerability_score or 0.0),
                 c.canonical_ref,
            ),
        )
        selected = tuple(candidates[: max(1, int(request.candidate_limit))])
        debug['candidate_count']   = len(selected)
        debug['candidate_origins'] = [c.retrieval_origin for c in selected]
        debug['top_refs']          = [c.canonical_ref for c in selected[:5]]

        return HadithTopicalCandidateGenerationResult(
            candidates=selected,
            warnings=tuple(dict.fromkeys(warnings)),
            debug=debug,
        )

    def _fetch_bukhari_hybrid(
        self,
        *,
        resolution: TopicResolution,
        dalil_family: str | None,
        size: int,
        enforce_primary: bool,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None, str | None, bool]:
        """Run BM25 + optional kNN against the Bukhari v2 index.

        Returns (bm25_hits, knn_hits, bm25_error, knn_error, knn_attempted).
        """
        bm25_hits: list[dict[str, Any]] = []
        knn_hits:  list[dict[str, Any]] = []
        bm25_err: str | None = None
        knn_err:  str | None = None
        knn_attempted = False

        # BM25
        try:
            body = build_bukhari_bm25_query(
                resolution=resolution,
                dalil_family=dalil_family,
                size=size,
                enforce_primary=enforce_primary,
            )
            resp = self.opensearch_client.search(index=HADITH_BUKHARI_TOPICAL_INDEX, body=body)
            bm25_hits = (((resp or {}).get('hits') or {}).get('hits') or [])
        except Exception as exc:
            bm25_err = str(exc)

        # kNN — only when we have an embedding
        embed_text = resolution.normalized_query or ' '.join(resolution.stripped_tokens)
        qvec = _get_query_embedding(embed_text) if embed_text else None
        if qvec:
            knn_attempted = True
            try:
                body = build_bukhari_knn_query(
                    resolution=resolution,
                    query_vector=qvec,
                    dalil_family=dalil_family,
                    k=size,
                    enforce_primary=enforce_primary,
                )
                resp = self.opensearch_client.search(index=HADITH_BUKHARI_TOPICAL_INDEX, body=body)
                knn_hits = (((resp or {}).get('hits') or {}).get('hits') or [])
            except Exception as exc:
                knn_err = str(exc)

        return bm25_hits, knn_hits, bm25_err, knn_err, knn_attempted

    # ------------------------------------------------------------------
    # Helpers
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
