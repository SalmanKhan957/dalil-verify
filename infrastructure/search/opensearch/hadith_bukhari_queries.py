"""OpenSearch query builders for the Bukhari topical v2 index.

Builds well-formed request bodies against `dalil-hadith-bukhari-topical-v2`
(aliased as `dalil-hadith-bukhari-topical`). Does not execute queries, fuse
results, or map hits — all of that lives in candidate_generation.py.

Major changes from the v1 builder:

    * `_CONCEPT_ALIASES`, `_STOP_PHRASES`, `_STOP_WORDS`, `_strip_fluff`,
      `_expand_concepts`, `prepare_search_terms` — all DELETED. Query
      normalization now lives in `domains.hadith_topical.query_topic_resolver`,
      which feeds a `TopicResolution` into these builders.
    * New first-class index fields used:
        - `primary_topics` (keyword, multi)     — hard filter target
        - `secondary_topics` (keyword, multi)   — soft boost via should clause
        - `concept_vocabulary` (text, english)  — highest-boost BM25 target,
                                                  corpus-grounded replacement
                                                  for the old alias dictionary
        - `matn_text_clean` (text, english)     — narrator-stripped body text,
                                                  replaces the dirty `matn_text`
    * `narrator` is explicitly NOT searched — it remains a keyword for
      citation/metadata only. Same rule at the data layer (matn_text_clean
      stripped "Narrated X:" fragments) and at the index layer.

All callers must pass a `TopicResolution`; the query builder does not
tokenise or strip queries itself any longer.
"""
from __future__ import annotations

from typing import Any

from domains.hadith_topical.query_topic_resolver import TopicResolution


# ---------------------------------------------------------------------------
# Family normalisation — DALIL query families → Bukhari index family
# ---------------------------------------------------------------------------

_DALIL_FAMILY_TO_BUKHARI: dict[str, str] = {
    'akhlaq':             'akhlaq',
    'adab':               'akhlaq',
    'moral_guidance':     'akhlaq',
    'character':          'akhlaq',
    'virtue':             'akhlaq',
    'ritual':             'ritual',
    'ritual_practice':    'ritual',
    'ibadah':             'ritual',
    'salah':              'ritual',
    'sawm':               'ritual',
    'zakat':              'ritual',
    'hajj':               'ritual',
    'fiqh':               'fiqh',
    'halal_haram':        'fiqh',
    'legal':              'fiqh',
    'marriage_divorce':   'fiqh',
    'zina':               'fiqh',
    'hudood':             'fiqh',
    'punishment':         'fiqh',
    'hadd':               'fiqh',
    'riba':               'fiqh',
    'trade':              'fiqh',
    'contract':           'fiqh',
    'inheritance':        'fiqh',
    'historical':         'historical',
    'seerah':             'historical',
    'narrative_event':    'historical',
    'eschatology':        'eschatology',
    'entity_eschatology': 'eschatology',
    'fitan':              'eschatology',
    'end_times':          'eschatology',
    'judgement':          'eschatology',
    'resurrection':       'eschatology',
    'akhirah':            'eschatology',
    'aqeedah':            'aqeedah',
    'belief':             'aqeedah',
    'tawhid':             'aqeedah',
    'quran':              'quran',
    'tafsir':             'quran',
    'foundational':       'foundational',
    'usul':               'foundational',
}


def normalise_family(dalil_family: str | None) -> str | None:
    if not dalil_family:
        return None
    return _DALIL_FAMILY_TO_BUKHARI.get(str(dalil_family).strip().lower())


# ---------------------------------------------------------------------------
# Shared filter construction
# ---------------------------------------------------------------------------

def _build_filter_clauses(
    resolution: TopicResolution,
    *,
    dalil_family: str | None,
    enforce_primary: bool,
) -> list[dict[str, Any]]:
    """Construct the list of filter clauses shared by BM25 and kNN queries.

    Filters are HARD — a document must satisfy every one to appear in results.
    The primary_topics filter is the product's strongest narrowing tool:
    zina queries only see zina-labelled records, Dajjal queries only see
    Dajjal-labelled records. When the resolver couldn't confidently pick a
    single slug, the filter relaxes to family-only so retrieval still works.
    """
    filters: list[dict[str, Any]] = [{'term': {'is_stub': False}}]

    has_primary = bool(enforce_primary and resolution.primary_topic)

    # When primary_topic is enforced, it is already the strictest possible
    # narrowing. Adding a query_family filter on top is redundant AND harmful
    # when the upstream classifier's family hint conflicts with the taxonomy
    # family (e.g. the classifier labels intentions as `moral_guidance`→`akhlaq`
    # while the correct taxonomy family is `foundational`). Only apply the
    # family filter on the fallback path where no primary topic was resolved.
    bukhari_family = normalise_family(dalil_family)
    if bukhari_family and not has_primary:
        filters.append({'term': {'query_family': bukhari_family}})

    if has_primary:
        filters.append({'term': {'primary_topics': resolution.primary_topic}})

    return filters


def _build_should_clauses(resolution: TopicResolution) -> list[dict[str, Any]]:
    """Construct the BM25 should clauses.

    Scoring stack (highest boost first):
      1. `concept_vocabulary` phrase match  — corpus-grounded, strongest signal
      2. `concept_vocabulary` AND match     — still corpus-grounded, looser
      3. `synthetic_baab_label` phrase      — chapter-title anchor
      4. `synthetic_baab_label` AND match   — chapter-title with word flex
      5. `matn_text_clean` AND match        — body text fallback
      6. `secondary_topics` boost           — soft alignment with near-miss slugs
    """
    tokens = resolution.stripped_tokens
    if not tokens:
        return [{'match_all': {}}]

    term_text = ' '.join(tokens)
    clauses: list[dict[str, Any]] = []

    # 1 & 2 — concept_vocabulary (corpus translation phrases)
    clauses.append({
        'match_phrase': {'concept_vocabulary': {'query': term_text, 'boost': 8.0}},
    })
    clauses.append({
        'match': {'concept_vocabulary': {'query': term_text, 'boost': 5.0, 'operator': 'and'}},
    })
    # 3 & 4 — synthetic_baab_label (chapter anchor)
    clauses.append({
        'match_phrase': {'synthetic_baab_label': {'query': term_text, 'boost': 4.0}},
    })
    clauses.append({
        'match': {'synthetic_baab_label': {'query': term_text, 'boost': 2.5, 'operator': 'and'}},
    })
    # 5 — matn_text_clean (body)
    clauses.append({
        'match': {'matn_text_clean': {'query': term_text, 'boost': 1.0, 'operator': 'and'}},
    })
    # 6 — secondary_topics soft boost (small; shouldn't dominate)
    for slug in resolution.secondary_topics[:3]:
        clauses.append({'term': {'secondary_topics': {'value': slug, 'boost': 0.5}}})
    # Near-tie confident topics also get a soft boost so they rank up even if
    # the primary filter is enforcing a single slug.
    for slug in resolution.confident_topics[1:3]:
        clauses.append({'term': {'secondary_topics': {'value': slug, 'boost': 0.5}}})

    return clauses


# ---------------------------------------------------------------------------
# BM25 query
# ---------------------------------------------------------------------------

def build_bukhari_bm25_query(
    *,
    resolution: TopicResolution,
    dalil_family: str | None = None,
    size: int = 20,
    enforce_primary: bool = True,
) -> dict[str, Any]:
    """Build a BM25 query body against the Bukhari topical v2 index.

    Args:
        resolution         — TopicResolution from query_topic_resolver.
        dalil_family       — DALIL family hint (translated to Bukhari family).
        size               — number of hits to return.
        enforce_primary    — when False, the primary_topics filter is dropped
                             even if the resolver found one. Useful for
                             fallback retrieval when a strict-filtered query
                             produced no hits.
    """
    filters = _build_filter_clauses(resolution, dalil_family=dalil_family, enforce_primary=enforce_primary)
    shoulds = _build_should_clauses(resolution)

    # When we have a confident primary_topic filter OR any hard filter at all,
    # `should` clauses are used purely for scoring — not for eligibility. We
    # deliberately drop minimum_should_match so records that match the filter
    # but don't hit any should-level AND clause still return (ranked lower,
    # but present). Without this, "rulings on riba" returns zero hits even
    # though 32 records carry primary_topics=fiqh.business.riba_usury, because
    # the word "rulings" isn't in those records' concept_vocabulary.
    has_filter = len(filters) > 1  # more than just is_stub
    minimum_should = 0 if has_filter else 1

    return {
        'size': max(1, int(size)),
        'query': {
            'bool': {
                'filter': filters,
                'should': shoulds,
                'minimum_should_match': minimum_should,
            },
        },
        '_source': {'excludes': ['matn_embedding']},
    }


# ---------------------------------------------------------------------------
# kNN query
# ---------------------------------------------------------------------------

def build_bukhari_knn_query(
    *,
    resolution: TopicResolution,
    query_vector: list[float],
    dalil_family: str | None = None,
    k: int = 20,
    enforce_primary: bool = True,
) -> dict[str, Any]:
    """Build a kNN query body against the matn_embedding field.

    Applies the SAME filter stack as the BM25 lane so RRF fuses across a
    consistent candidate pool. The kNN filter clause uses OpenSearch's
    `filter` sub-clause on the knn query — effective on Lucene engine
    and supported on the current index (see build_bukhari_topical_v2_index).
    """
    filters = _build_filter_clauses(resolution, dalil_family=dalil_family, enforce_primary=enforce_primary)

    knn_field: dict[str, Any] = {
        'vector': query_vector,
        'k':      max(1, int(k)),
    }
    if filters:
        knn_field['filter'] = {'bool': {'must': filters}}

    return {
        'size': max(1, int(k)),
        'query': {
            'knn': {
                'matn_embedding': knn_field,
            },
        },
        '_source': {'excludes': ['matn_embedding']},
    }
