"""OpenSearch query builders for the Bukhari topical hybrid index.

This module is exclusively responsible for constructing well-formed OpenSearch
query bodies against `hadith_topical_bukhari`.  It does not execute queries,
combine results, or map hits — all of that belongs in candidate_generation.py.

Index fields used:
    synthetic_baab_label  — text, english analyzer, boost target for BM25
    matn_text             — text, english analyzer, main content
    query_family          — keyword, pre-filter
    is_stub               — boolean, mandatory exclusion filter
    has_direct_prophetic_statement — boolean, available for score-time boost
    matn_embedding        — knn_vector(1536), dense retrieval target
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Family normalisation
# ---------------------------------------------------------------------------

# Map DALIL's internal family IDs (from query_family_classifier) to the eight
# query_family keyword values stored in the Bukhari index.
# Unmapped families fall through to None → pre-filter is omitted (wider search).
_DALIL_FAMILY_TO_BUKHARI: dict[str, str] = {
    # akhlaq / moral guidance
    'akhlaq': 'akhlaq',
    'adab': 'akhlaq',
    'moral_guidance': 'akhlaq',
    'character': 'akhlaq',
    'virtue': 'akhlaq',
    # ritual / ibadah
    'ritual': 'ritual',
    'ritual_practice': 'ritual',
    'ibadah': 'ritual',
    'salah': 'ritual',
    'sawm': 'ritual',
    'zakat': 'ritual',
    'hajj': 'ritual',
    # fiqh / legal
    'fiqh': 'fiqh',
    'halal_haram': 'fiqh',
    'legal': 'fiqh',
    # historical / seerah
    'historical': 'historical',
    'seerah': 'historical',
    'narrative_event': 'historical',
    # eschatology / fitan
    'eschatology': 'eschatology',
    'entity_eschatology': 'eschatology',
    'fitan': 'eschatology',
    'end_times': 'eschatology',
    'judgement': 'eschatology',      # <--- ADD THIS
    'resurrection': 'eschatology',   # <--- ADD THIS
    'akhirah': 'eschatology',
    # aqeedah / belief
    'aqeedah': 'aqeedah',
    'belief': 'aqeedah',
    'tawhid': 'aqeedah',
    # quran-related
    'quran': 'quran',
    'tafsir': 'quran',
    # foundational
    'foundational': 'foundational',
    'usul': 'foundational',
}


def normalise_family(dalil_family: str | None) -> str | None:
    """Return the Bukhari index query_family value for a DALIL family ID.

    Returns None when the family is unmapped so callers can decide whether to
    omit the filter (wider search) rather than filter on a wrong value.
    """
    if not dalil_family:
        return None
    return _DALIL_FAMILY_TO_BUKHARI.get(str(dalil_family).strip().lower())


# ---------------------------------------------------------------------------
# BM25 query
# ---------------------------------------------------------------------------

def build_bukhari_bm25_query(
    *,
    normalized_query: str,
    topic_candidates: tuple[str, ...] = (),
    dalil_family: str | None = None,
    size: int = 20,
) -> dict[str, Any]:
    """Build a BM25 bool query against hadith_topical_bukhari.

    Scoring strategy:
        synthetic_baab_label  — boosted 2.0  (chapter-level signal)
        matn_text             — boosted 1.0  (full hadith text)
        + per-topic term boosts on both fields

    Mandatory filter:
        is_stub = false       — always applied

    Optional pre-filter:
        query_family          — applied when a known Bukhari family is resolved
    """
    bukhari_family = normalise_family(dalil_family)

    must_filters: list[dict[str, Any]] = [
        {'term': {'is_stub': False}},
    ]
    if bukhari_family:
        must_filters.append({'term': {'query_family': bukhari_family}})

    should: list[dict[str, Any]] = []

    if normalized_query:
        should.append({
            'match_phrase': {
                'synthetic_baab_label': {
                    'query': normalized_query,
                    'boost': 3.0,
                },
            },
        })
        should.append({
            'match': {
                'synthetic_baab_label': {
                    'query': normalized_query,
                    'analyzer': 'english',
                    'boost': 2.0,
                },
            },
        })
        should.append({
            'match': {
                'matn_text': {
                    'query': normalized_query,
                    'analyzer': 'english',
                    'boost': 1.0,
                },
            },
        })

    for topic in topic_candidates:
        if not topic:
            continue
        # Exact term match on baab label is a strong topical signal
        should.append({
            'match': {
                'synthetic_baab_label': {
                    'query': topic,
                    'boost': 1.8,
                },
            },
        })
        should.append({
            'match': {
                'matn_text': {
                    'query': topic,
                    'boost': 1.2,
                },
            },
        })

    return {
        'size': max(1, int(size)),
        'query': {
            'bool': {
                'filter': must_filters,
                'should': should or [{'match_all': {}}],
                'minimum_should_match': 1,
            },
        },
        '_source': {
            'excludes': ['matn_embedding'],   # never return the vector in hits
        },
    }


# ---------------------------------------------------------------------------
# kNN query
# ---------------------------------------------------------------------------

def build_bukhari_knn_query(
    *,
    query_vector: list[float],
    dalil_family: str | None = None,
    k: int = 20,
) -> dict[str, Any]:
    """Build a kNN query against the matn_embedding field.

    Uses OpenSearch 2.x knn query syntax with an inline filter.
    The filter is applied as a pre-filter (not post-filter) for correctness
    and performance.

    Args:
        query_vector:  Dense embedding of the normalised user query.
                       Must match the dimension used at index build time (1536).
        dalil_family:  DALIL family ID used to resolve the Bukhari query_family
                       pre-filter.  Omitted when None or unmapped.
        k:             Number of approximate nearest neighbours to retrieve.
    """
    bukhari_family = normalise_family(dalil_family)

    knn_filter_clauses: list[dict[str, Any]] = [
        {'term': {'is_stub': False}},
    ]
    if bukhari_family:
        knn_filter_clauses.append({'term': {'query_family': bukhari_family}})

    knn_field: dict[str, Any] = {
        'vector': query_vector,
        'k': max(1, int(k)),
    }
    if knn_filter_clauses:
        knn_field['filter'] = {
            'bool': {'must': knn_filter_clauses},
        }

    return {
        'size': max(1, int(k)),
        'query': {
            'knn': {
                'matn_embedding': knn_field,
            },
        },
        '_source': {
            'excludes': ['matn_embedding'],
        },
    }
