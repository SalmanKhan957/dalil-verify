"""Build the hadith_topical_bukhari OpenSearch index from the ingested DB.

Usage:
    python -m pipelines.hadith_topical.build_bukhari_topical_index

Environment variables (inherit from DALIL deployment config):
    OPENSEARCH_URL          required
    OPENSEARCH_USERNAME     optional
    OPENSEARCH_PASSWORD     optional
    DATABASE_URL            required (or DALIL DB env vars)
    OPENSEARCH_VERIFY_SSL   optional, default true

The script is idempotent:
    - If the index already exists it is deleted and rebuilt from scratch.
    - Documents are bulk-indexed in batches of BATCH_SIZE.
    - Stub records (is_stub = true) are excluded.

The script does NOT manage embeddings.  If matn_text embeddings are available
in the database (via a metadata_json key 'matn_embedding'), they are included.
If not present, the knn_vector field is left unpopulated for that document
and only BM25 retrieval will work until embeddings are backfilled.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from infrastructure.db.session import get_session
from infrastructure.search.index_names import HADITH_BUKHARI_TOPICAL_INDEX
from infrastructure.search.opensearch_client import OpenSearchClient

log = logging.getLogger(__name__)

BATCH_SIZE = 200

# ---------------------------------------------------------------------------
# Index mapping
# ---------------------------------------------------------------------------

# Embedding dimension must match the model used throughout DALIL.
# Adjust this constant if the embedding model changes.
_EMBEDDING_DIM = 1536

_INDEX_MAPPING: dict[str, Any] = {
    'settings': {
        'index.knn': True
    },
    'mappings': {
        'properties': {
            'hadith_id': {'type': 'keyword'},
            'hadith_global_num': {'type': 'integer'},
            'kitab_num': {'type': 'integer'},
            'kitab_title_english': {'type': 'keyword'},
            'kitab_range_start': {'type': 'integer'},
            'kitab_range_end': {'type': 'integer'},
            'query_family': {'type': 'keyword'},
            'kitab_domain': {'type': 'keyword'},
            'synthetic_baab_label': {
                'type': 'text',
                'analyzer': 'english',
            },
            'synthetic_baab_id': {'type': 'keyword'},
            'has_direct_prophetic_statement': {'type': 'boolean'},
            'is_stub': {'type': 'boolean'},
            'narrator': {'type': 'keyword'},
            'matn_text': {
                'type': 'text',
                'analyzer': 'english',
            },
            'matn_embedding': {
                'type': 'knn_vector',
                'dimension': _EMBEDDING_DIM,
                'method': {
                    'name': 'hnsw',
                    'space_type': 'cosinesimil',  # <--- THIS WAS THE CULPRIT
                    'engine': 'lucene',
                    'parameters': {
                        'ef_construction': 128,
                        'm': 16,
                    },
                },
            },
            'reference_url': {'type': 'keyword'},
            'in_book_reference': {'type': 'keyword'},
        },
    },
}


# ---------------------------------------------------------------------------
# DB fetch
# ---------------------------------------------------------------------------

def _fetch_bukhari_records(database_url: str | None = None) -> list[dict[str, Any]]:
    """Fetch all non-stub Bukhari hadith from the canonical DB table.

    Returns a list of flat dicts ready for OpenSearch indexing.
    Embeddings are included from metadata_json['matn_embedding'] when present.
    """
    from sqlalchemy import text as sa_text

    records: list[dict[str, Any]] = []

    with get_session(database_url=database_url) as session:
        # Join hadith_entries with source_works to filter by collection
        stmt = sa_text("""
            SELECT
                he.id,
                he.canonical_ref_collection AS hadith_id,
                he.collection_hadith_number AS hadith_global_num,
                he.upstream_book_id         AS kitab_num,
                he.english_text             AS matn_text,
                he.english_narrator         AS narrator,
                he.metadata_json
            FROM hadith_entries he
            JOIN source_works sw ON he.work_id = sw.id
            WHERE sw.source_id = 'hadith:sahih-al-bukhari-en'
              AND he.metadata_json->>'is_stub' IS DISTINCT FROM 'true'
            ORDER BY he.collection_hadith_number
        """)

        rows = session.execute(stmt).fetchall()
        log.info('Fetched %d Bukhari records from DB.', len(rows))

        for row in rows:
            entry_id, hadith_id, hadith_global_num, kitab_num, matn_text, narrator, metadata_json_raw = row

            if not hadith_id or not matn_text:
                continue

            meta: dict[str, Any] = {}
            if metadata_json_raw:
                try:
                    meta = json.loads(metadata_json_raw) if isinstance(metadata_json_raw, str) else dict(metadata_json_raw)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Guard: skip stubs that slipped through the SQL filter
            if meta.get('is_stub'):
                continue

            doc: dict[str, Any] = {
                'hadith_id': str(hadith_id),
                'hadith_global_num': int(hadith_global_num or 0),
                'kitab_num': int(kitab_num or 0),
                'kitab_title_english': str(meta.get('kitab_title_english') or ''),
                'kitab_range_start': int(meta.get('kitab_range_start') or 0),
                'kitab_range_end': int(meta.get('kitab_range_end') or 0),
                'query_family': str(meta.get('query_family') or ''),
                'kitab_domain': list(meta.get('kitab_domain') or []),
                'synthetic_baab_label': str(meta.get('synthetic_baab_label') or ''),
                'synthetic_baab_id': str(meta.get('synthetic_baab_id') or '') or None,
                'has_direct_prophetic_statement': bool(meta.get('has_direct_prophetic_statement', False)),
                'is_stub': False,
                'narrator': str(narrator or ''),
                'matn_text': str(matn_text or ''),
                'reference_url': str(meta.get('reference_url') or '') or None,
                'in_book_reference': str(meta.get('in_book_reference') or '') or None,
            }

            # Include embedding if available — do not generate here
            embedding = meta.get('matn_embedding')
            if embedding and isinstance(embedding, list) and len(embedding) == _EMBEDDING_DIM:
                doc['matn_embedding'] = embedding

            records.append(doc)

    return records


# ---------------------------------------------------------------------------
# Index lifecycle
# ---------------------------------------------------------------------------

def _recreate_index(client: OpenSearchClient) -> None:
    """Drop and recreate the Bukhari topical index."""
    index = HADITH_BUKHARI_TOPICAL_INDEX

    # Delete if exists
    try:
        existing = client._request('HEAD', f'/{index}', allow_404=True)
        if existing.get('status_code') == 200:
            log.info('Deleting existing index %s …', index)
            client._request('DELETE', f'/{index}')
    except Exception as exc:
        log.warning('Could not check/delete existing index: %s', exc)

    log.info('Creating index %s …', index)
    client.create_index(index=index, body=_INDEX_MAPPING)
    log.info('Index %s created.', index)


def _bulk_index_records(
    client: OpenSearchClient,
    records: list[dict[str, Any]],
    batch_size: int = BATCH_SIZE,
) -> int:
    """Bulk-index records in batches.  Returns total documents indexed."""
    total = 0
    for offset in range(0, len(records), batch_size):
        batch = records[offset : offset + batch_size]
        result = client.bulk_index(
            index=HADITH_BUKHARI_TOPICAL_INDEX,
            documents=batch,
            id_field='hadith_id',
        )
        errors = result.get('errors', False)
        if errors:
            # Surface the first failing item for diagnosis
            items = result.get('items') or []
            for item in items:
                op = item.get('index') or {}
                if op.get('error'):
                    log.error('Bulk index error on %s: %s', op.get('_id'), op['error'])
                    break
        total += len(batch)
        log.info('Indexed batch %d–%d (%d total so far).', offset + 1, offset + len(batch), total)

    return total


# ---------------------------------------------------------------------------
# Verification queries
# ---------------------------------------------------------------------------

_VERIFICATION_QUERIES: list[dict[str, Any]] = [
    {
        'label': 'anger → bukhari:6116',
        'query': {
            'size': 1,
            'query': {
                'bool': {
                    'filter': [{'term': {'is_stub': False}}],
                    'should': [
                        {'match': {'synthetic_baab_label': {'query': 'anger self control', 'boost': 2.0}}},
                        {'match': {'matn_text': {'query': 'do not become angry', 'boost': 1.0}}},
                    ],
                    'minimum_should_match': 1,
                },
            },
        },
        'expected_id': 'bukhari:6116',
    },
    {
        'label': 'lying → bukhari:6094 or bukhari:6095',
        'query': {
            'size': 1,
            'query': {
                'bool': {
                    'filter': [{'term': {'is_stub': False}}],
                    'should': [
                        {'match': {'synthetic_baab_label': {'query': 'lying dishonesty', 'boost': 2.0}}},
                        {'match': {'matn_text': {'query': 'lying false', 'boost': 1.0}}},
                    ],
                    'minimum_should_match': 1,
                },
            },
        },
        'expected_family': 'akhlaq',
    },
    {
        'label': 'signs of Hour → kitab_num 92',
        'query': {
            'size': 1,
            'query': {
                'bool': {
                    'filter': [
                        {'term': {'is_stub': False}},
                        {'term': {'query_family': 'eschatology'}},
                    ],
                    'should': [
                        {'match': {'synthetic_baab_label': {'query': 'afflictions trials fitan', 'boost': 2.0}}},
                        {'match': {'matn_text': {'query': 'afflictions sitting standing walking', 'boost': 1.0}}},
                    ],
                    'minimum_should_match': 1,
                },
            },
        },
        'expected_kitab': 92,
    },
    {
        'label': 'patience hardship → family akhlaq',
        'query': {
            'size': 1,
            'query': {
                'bool': {
                    'filter': [
                        {'term': {'is_stub': False}},
                        {'term': {'query_family': 'akhlaq'}},
                    ],
                    'should': [
                        {'match': {'synthetic_baab_label': {'query': 'patience trials endurance', 'boost': 2.0}}},
                        {'match': {'matn_text': {'query': 'patience hardship trials', 'boost': 1.0}}},
                    ],
                    'minimum_should_match': 1,
                },
            },
        },
        'expected_family': 'akhlaq',
    },
]


def _run_verification(client: OpenSearchClient) -> bool:
    """Run the four spec verification queries.  Returns True if all pass."""
    all_passed = True
    log.info('\n=== Verification queries ===')

    for spec in _VERIFICATION_QUERIES:
        label = spec['label']
        try:
            resp = client.search(index=HADITH_BUKHARI_TOPICAL_INDEX, body=spec['query'])
            hits = (((resp or {}).get('hits') or {}).get('hits') or [])
            if not hits:
                log.error('FAIL [%s]: no hits returned.', label)
                all_passed = False
                continue
            top = hits[0].get('_source') or {}
            hadith_id = top.get('hadith_id', '')
            family = top.get('query_family', '')
            kitab_num = top.get('kitab_num')

            if 'expected_id' in spec and hadith_id != spec['expected_id']:
                log.warning(
                    'WARN [%s]: expected %s, got %s (may be acceptable if scores are close)',
                    label, spec['expected_id'], hadith_id,
                )
            elif 'expected_family' in spec and family != spec['expected_family']:
                log.error('FAIL [%s]: expected family %s, got %s.', label, spec['expected_family'], family)
                all_passed = False
            elif 'expected_kitab' in spec and kitab_num != spec['expected_kitab']:
                log.error('FAIL [%s]: expected kitab_num %s, got %s.', label, spec['expected_kitab'], kitab_num)
                all_passed = False
            else:
                log.info('PASS [%s]: top hit = %s (family=%s)', label, hadith_id, family)
        except Exception as exc:
            log.error('ERROR [%s]: %s', label, exc)
            all_passed = False

    return all_passed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(database_url: str | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

    client = OpenSearchClient.from_environment()
    if not client.is_enabled:
        log.error('OPENSEARCH_URL is not set.  Cannot build index.')
        sys.exit(1)

    log.info('Fetching Bukhari records from database …')
    records = _fetch_bukhari_records(database_url=database_url)
    if not records:
        log.error('No Bukhari records found in the database.  Aborting.')
        sys.exit(1)
    log.info('Found %d non-stub Bukhari records.', len(records))

    has_embeddings = sum(1 for r in records if 'matn_embedding' in r)
    log.info('%d / %d records have matn_embedding.', has_embeddings, len(records))
    if has_embeddings == 0:
        log.warning(
            'No embeddings found.  The index will be built with BM25 only.  '
            'Run the embedding backfill pipeline and rebuild to enable kNN retrieval.'
        )

    _recreate_index(client)
    total_indexed = _bulk_index_records(client, records)
    log.info('Bulk indexing complete.  %d documents indexed.', total_indexed)

    passed = _run_verification(client)
    if not passed:
        log.error('One or more verification queries failed.  Review index content before using in production.')
        sys.exit(2)

    log.info('All verification queries passed.  Index %s is ready.', HADITH_BUKHARI_TOPICAL_INDEX)


if __name__ == '__main__':
    main()
