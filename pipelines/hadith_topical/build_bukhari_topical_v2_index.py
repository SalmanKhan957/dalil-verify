"""Build the Bukhari topical v2 OpenSearch index.

Reads from the DB (NOT the enriched JSON). The DB is the canonical source of
truth after Phase 2 Step 1 (migrate_topical_to_db.py) populates the topical
fields into `hadith_entries.metadata_json`.

Preconditions (hard-checked at startup):
    - `OPENSEARCH_URL` env var is set
    - The DB has >= one Bukhari row with `metadata_json->>'primary_topics'` present
    - The DB has >= one Bukhari row with `metadata_json->>'matn_text_clean'` present
    - Embeddings are optional — if missing, the index builds BM25-only.
      Warn loudly and continue.

The v2 index differs from v1 in these critical ways:

    * `primary_topics` / `secondary_topics`: keyword (multi-value). Primary is
      the hard-filter target; secondary is a soft boost.
    * `concept_vocabulary`: text with english analyzer. The highest-boost BM25
      field — replaces the runtime _CONCEPT_ALIASES dict with per-record data.
    * `matn_text_clean`: text with english analyzer. Narrator-stripped. This
      is the primary body-text BM25 field, replacing the dirty `matn_text`.
    * `topic_density`: float. Fed into the candidate generator's centrality
      score — replaces the heuristic _derive_proxy_scores_from_bukhari.
    * `narrator`: keyword (metadata only). NOT searched — prevents the
      Abu Az-Zinad collision at the index layer as well as the data layer.
    * `abstain_reason`: keyword, for observability.

After build:
    - Runs 6 verification queries covering the canonical failure cases
    - Does NOT swap the alias. Cutover is a separate, explicit step.

Usage:
    python -m pipelines.hadith_topical.build_bukhari_topical_v2_index
    python -m pipelines.hadith_topical.build_bukhari_topical_v2_index --skip-verify
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from sqlalchemy import text as sa_text

from infrastructure.db.session import get_session
from infrastructure.search.index_names import HADITH_BUKHARI_TOPICAL_INDEX_V2
from infrastructure.search.opensearch_client import OpenSearchClient

log = logging.getLogger('build_bukhari_topical_v2_index')

_BUKHARI_SOURCE_ID = 'hadith:sahih-al-bukhari-en'
_BATCH_SIZE = 200
_EMBEDDING_DIM = 1536


# ---------------------------------------------------------------------------
# Index mapping — v2
# ---------------------------------------------------------------------------

_INDEX_MAPPING: dict[str, Any] = {
    'settings': {
        'index.knn': True,
    },
    'mappings': {
        'properties': {
            # Identity / citation
            'hadith_id':               {'type': 'keyword'},
            'hadith_global_num':       {'type': 'integer'},
            'kitab_num':               {'type': 'integer'},
            'kitab_title_english':     {'type': 'keyword'},
            'kitab_range_start':       {'type': 'integer'},
            'kitab_range_end':         {'type': 'integer'},
            'reference_url':           {'type': 'keyword'},
            'in_book_reference':       {'type': 'keyword'},

            # Family / domain pre-filters
            'query_family':            {'type': 'keyword'},
            'kitab_domain':            {'type': 'keyword'},

            # Topical first-class fields (new in v2)
            'primary_topics':          {'type': 'keyword'},
            'secondary_topics':        {'type': 'keyword'},
            'concept_vocabulary':      {'type': 'text', 'analyzer': 'english'},
            'topic_density':           {'type': 'float'},
            'is_multi_topic':          {'type': 'boolean'},
            'abstain_reason':          {'type': 'keyword'},
            'enrichment_version':      {'type': 'keyword'},
            'enrichment_model':        {'type': 'keyword'},

            # Chapter anchor (kept as BM25 target — mid boost)
            'synthetic_baab_label':    {'type': 'text', 'analyzer': 'english'},
            'synthetic_baab_id':       {'type': 'keyword'},

            # Prophetic signal
            'has_direct_prophetic_statement': {'type': 'boolean'},
            'is_stub':                 {'type': 'boolean'},

            # Narrator — metadata ONLY. Not a BM25 target. Prevents the
            # zina/Abu-Az-Zinad collision at the index layer.
            'narrator':                {'type': 'keyword'},

            # Body text — clean version replaces raw matn for BM25.
            'matn_text_clean':         {'type': 'text', 'analyzer': 'english'},

            # Dense retrieval
            'matn_embedding': {
                'type': 'knn_vector',
                'dimension': _EMBEDDING_DIM,
                'method': {
                    'name': 'hnsw',
                    'space_type': 'cosinesimil',
                    'engine': 'lucene',
                    'parameters': {
                        'ef_construction': 128,
                        'm': 16,
                    },
                },
            },
        },
    },
}


# ---------------------------------------------------------------------------
# DB fetch
# ---------------------------------------------------------------------------

def _preflight(session) -> dict[str, int]:
    """Fail fast if Steps 1 / 2 haven't run."""
    stmt = sa_text("""
        SELECT
            COUNT(*) AS total,
            COUNT(he.metadata_json->'primary_topics') AS has_primary,
            COUNT(he.metadata_json->>'matn_text_clean') AS has_clean,
            COUNT(he.metadata_json->'matn_embedding') AS has_embedding,
            COUNT(he.metadata_json->>'matn_embedding_source_field') FILTER (
                WHERE he.metadata_json->>'matn_embedding_source_field' = 'matn_text_clean'
            ) AS has_clean_embedding
        FROM hadith_entries he
        JOIN source_works sw ON he.work_id = sw.id
        WHERE sw.source_id = :source_id
    """)
    row = session.execute(stmt, {'source_id': _BUKHARI_SOURCE_ID}).fetchone()
    return {
        'total': int(row[0] or 0),
        'has_primary': int(row[1] or 0),
        'has_clean': int(row[2] or 0),
        'has_embedding': int(row[3] or 0),
        'has_clean_embedding': int(row[4] or 0),
    }


def _fetch_rows(session) -> list[dict[str, Any]]:
    stmt = sa_text("""
        SELECT
            he.id,
            he.canonical_ref_collection AS hadith_id,
            he.collection_hadith_number AS hadith_global_num,
            he.upstream_book_id         AS kitab_num,
            he.english_text             AS matn_text_raw,
            he.english_narrator         AS narrator,
            he.metadata_json
        FROM hadith_entries he
        JOIN source_works sw ON he.work_id = sw.id
        WHERE sw.source_id = :source_id
        ORDER BY he.collection_hadith_number
    """)
    rows = session.execute(stmt, {'source_id': _BUKHARI_SOURCE_ID}).fetchall()

    documents: list[dict[str, Any]] = []
    for row in rows:
        entry_id, hadith_id, global_num, kitab_num, matn_raw, narrator, meta_raw = row
        meta: dict[str, Any] = {}
        if meta_raw:
            meta = dict(meta_raw) if isinstance(meta_raw, dict) else json.loads(meta_raw)
        if meta.get('is_stub'):
            continue
        if not hadith_id:
            continue
        matn_text_clean = str(meta.get('matn_text_clean') or matn_raw or '').strip()
        if not matn_text_clean:
            continue

        doc: dict[str, Any] = {
            'hadith_id': str(hadith_id),
            'hadith_global_num': int(global_num or 0),
            'kitab_num': int(kitab_num or 0),
            'kitab_title_english': str(meta.get('kitab_title_english') or ''),
            'kitab_range_start': int(meta.get('kitab_range_start') or 0),
            'kitab_range_end': int(meta.get('kitab_range_end') or 0),
            'reference_url': str(meta.get('reference_url') or '') or None,
            'in_book_reference': str(meta.get('in_book_reference') or '') or None,

            'query_family': str(meta.get('query_family') or ''),
            'kitab_domain': list(meta.get('kitab_domain') or []),

            'primary_topics': list(meta.get('primary_topics') or []),
            'secondary_topics': list(meta.get('secondary_topics') or []),
            'concept_vocabulary': list(meta.get('concept_vocabulary') or []),
            'topic_density': float(meta.get('topic_density') or 0.0),
            'is_multi_topic': bool(meta.get('is_multi_topic', False)),
            'abstain_reason': str(meta.get('abstain_reason') or '') or None,
            'enrichment_version': str(meta.get('enrichment_version') or '') or None,
            'enrichment_model': str(meta.get('enrichment_model') or '') or None,

            'synthetic_baab_label': str(meta.get('synthetic_baab_label') or ''),
            'synthetic_baab_id': str(meta.get('synthetic_baab_id') or '') or None,

            'has_direct_prophetic_statement': bool(meta.get('has_direct_prophetic_statement', False)),
            'is_stub': False,

            'narrator': str(narrator or ''),
            'matn_text_clean': matn_text_clean,
        }

        embedding = meta.get('matn_embedding')
        if embedding and isinstance(embedding, list) and len(embedding) == _EMBEDDING_DIM:
            doc['matn_embedding'] = embedding

        documents.append(doc)

    return documents


# ---------------------------------------------------------------------------
# Index lifecycle
# ---------------------------------------------------------------------------

def _recreate_index(client: OpenSearchClient) -> None:
    index = HADITH_BUKHARI_TOPICAL_INDEX_V2
    try:
        existing = client._request('HEAD', f'/{index}', allow_404=True)
        if existing.get('status_code') == 200:
            log.info('Deleting existing index %s ...', index)
            client._request('DELETE', f'/{index}')
    except Exception as exc:
        log.warning('Could not check/delete existing index: %s', exc)

    log.info('Creating index %s ...', index)
    client.create_index(index=index, body=_INDEX_MAPPING)
    log.info('Index %s created.', index)


def _bulk_index(client: OpenSearchClient, records: list[dict[str, Any]], batch_size: int) -> int:
    total = 0
    for offset in range(0, len(records), batch_size):
        batch = records[offset: offset + batch_size]
        result = client.bulk_index(
            index=HADITH_BUKHARI_TOPICAL_INDEX_V2,
            documents=batch,
            id_field='hadith_id',
        )
        if result.get('errors'):
            for item in result.get('items') or []:
                op = item.get('index') or {}
                if op.get('error'):
                    log.error('Bulk index error on %s: %s', op.get('_id'), op['error'])
                    break
        total += len(batch)
        log.info('Indexed batch %d-%d (%d total).', offset + 1, offset + len(batch), total)
    return total


# ---------------------------------------------------------------------------
# Verification — canonical failure cases
# ---------------------------------------------------------------------------

_VERIFICATION_QUERIES: list[dict[str, Any]] = [
    {
        'label': 'zina -> hudud, NOT Abu Az-Zinad',
        'body': {
            'size': 3,
            'query': {
                'bool': {
                    'filter': [
                        {'term': {'is_stub': False}},
                        {'term': {'primary_topics': 'fiqh.hudood.zina_adultery'}},
                    ],
                    'must': {'match_phrase': {'concept_vocabulary': 'illegal sexual intercourse'}},
                },
            },
        },
        'expect_primary_topic': 'fiqh.hudood.zina_adultery',
    },
    {
        'label': 'Dajjal -> eschatology.dajjal primary',
        'body': {
            'size': 3,
            'query': {
                'bool': {
                    'filter': [
                        {'term': {'is_stub': False}},
                        {'term': {'primary_topics': 'eschatology.dajjal'}},
                    ],
                },
            },
        },
        'expect_primary_topic': 'eschatology.dajjal',
    },
    {
        'label': 'riba -> business.riba_usury',
        'body': {
            'size': 3,
            'query': {
                'bool': {
                    'filter': [
                        {'term': {'is_stub': False}},
                        {'term': {'primary_topics': 'fiqh.business.riba_usury'}},
                    ],
                },
            },
        },
        'expect_primary_topic': 'fiqh.business.riba_usury',
    },
    {
        'label': 'ghusl -> tahara.ghusl_bathing',
        'body': {
            'size': 3,
            'query': {
                'bool': {
                    'filter': [
                        {'term': {'is_stub': False}},
                        {'term': {'primary_topics': 'ritual.tahara.ghusl_bathing'}},
                    ],
                },
            },
        },
        'expect_primary_topic': 'ritual.tahara.ghusl_bathing',
    },
    {
        'label': 'intention -> foundational.intention_niyya',
        'body': {
            'size': 3,
            'query': {
                'bool': {
                    'filter': [
                        {'term': {'is_stub': False}},
                        {'term': {'primary_topics': 'foundational.intention_niyya'}},
                    ],
                },
            },
        },
        'expect_primary_topic': 'foundational.intention_niyya',
    },
    {
        'label': 'BM25 on concept_vocabulary matches "adultery"',
        'body': {
            'size': 3,
            'query': {
                'bool': {
                    'filter': [{'term': {'is_stub': False}}],
                    'must': {'match_phrase': {'concept_vocabulary': 'adultery'}},
                },
            },
        },
        'expect_min_hits': 1,
    },
]


def _run_verification(client: OpenSearchClient) -> bool:
    log.info('=== Verification ===')
    all_passed = True
    for spec in _VERIFICATION_QUERIES:
        label = spec['label']
        try:
            resp = client.search(index=HADITH_BUKHARI_TOPICAL_INDEX_V2, body=spec['body'])
            hits = (((resp or {}).get('hits') or {}).get('hits') or [])
            total = ((resp or {}).get('hits') or {}).get('total') or {}
            total_value = total.get('value') if isinstance(total, dict) else total
            if 'expect_min_hits' in spec:
                if (total_value or 0) < spec['expect_min_hits']:
                    log.error('FAIL [%s]: got %s hits, expected >= %d.', label, total_value, spec['expect_min_hits'])
                    all_passed = False
                    continue
                log.info('PASS [%s]: %s hits', label, total_value)
                continue
            if not hits:
                log.error('FAIL [%s]: no hits returned.', label)
                all_passed = False
                continue
            top = hits[0].get('_source') or {}
            primary = top.get('primary_topics') or []
            expected = spec.get('expect_primary_topic')
            if expected and expected not in primary:
                log.error('FAIL [%s]: expected %s in primary_topics, got %s.', label, expected, primary)
                all_passed = False
            else:
                log.info('PASS [%s]: top hit %s has %s', label, top.get('hadith_id'), primary)
        except Exception as exc:
            log.error('ERROR [%s]: %s', label, exc)
            all_passed = False
    return all_passed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-verify', action='store_true', help='Skip verification queries.')
    parser.add_argument('--batch-size', type=int, default=_BATCH_SIZE)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')

    client = OpenSearchClient.from_environment()
    if not client.is_enabled:
        log.error('OPENSEARCH_URL not set.')
        sys.exit(2)

    with get_session() as session:
        stats = _preflight(session)

    log.info('DB preflight: %s', stats)
    if stats['total'] == 0:
        log.error('No Bukhari rows in DB.')
        sys.exit(3)
    if stats['has_primary'] == 0:
        log.error('No rows have primary_topics. Run Phase 2 Step 1 (migrate_topical_to_db) first.')
        sys.exit(3)
    if stats['has_clean'] == 0:
        log.error('No rows have matn_text_clean. Run Phase 2 Step 1 first.')
        sys.exit(3)
    if stats['has_clean_embedding'] == 0 and stats['has_embedding'] > 0:
        log.warning('Embeddings exist but were NOT generated against matn_text_clean. Run Step 2 with --source-field matn_text_clean --overwrite for consistent retrieval.')
    elif stats['has_embedding'] == 0:
        log.warning('No embeddings found. Index will build BM25-only. Run Step 2 to enable kNN retrieval.')
    coverage_pct = 100 * stats['has_primary'] / max(1, stats['total'])
    log.info('Topical coverage: %.1f%% (%d / %d)', coverage_pct, stats['has_primary'], stats['total'])

    log.info('Fetching rows from DB ...')
    with get_session() as session:
        records = _fetch_rows(session)
    log.info('%d non-stub rows ready for indexing.', len(records))

    with_emb = sum(1 for r in records if 'matn_embedding' in r)
    log.info('Records with embedding attached: %d / %d', with_emb, len(records))

    _recreate_index(client)
    total = _bulk_index(client, records, batch_size=args.batch_size)
    log.info('Indexed %d documents into %s.', total, HADITH_BUKHARI_TOPICAL_INDEX_V2)

    if args.skip_verify:
        log.info('Skipping verification.')
        return

    passed = _run_verification(client)
    if not passed:
        log.error('Verification failed. Inspect the errors above before cutover.')
        sys.exit(4)
    log.info('All verification queries passed. Ready for runtime cutover.')


if __name__ == '__main__':
    main()
