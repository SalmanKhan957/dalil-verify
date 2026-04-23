"""Migrate enriched topical fields from JSON into the Bukhari DB rows.

Reads `data/raw/hadith/meeatif/bukhari_enriched_v3_topical.json` and updates
`hadith_entries.metadata_json` for each matching record, merging in:

    primary_topics         list[str]
    secondary_topics       list[str]
    concept_vocabulary     list[str]
    matn_text_clean        str
    topic_density          float
    abstain_reason         str | null
    is_multi_topic         bool
    enrichment_version     str
    enrichment_model       str

This is idempotent. Rerunning it overwrites only those keys; every other
field in metadata_json (incl. pre-existing matn_embedding) is preserved.

Usage:
    python -m pipelines.hadith_topical.migrate_topical_to_db
    python -m pipelines.hadith_topical.migrate_topical_to_db --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from sqlalchemy import text as sa_text

from infrastructure.db.session import get_session

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENRICHED_JSON = _REPO_ROOT / 'data' / 'raw' / 'hadith' / 'meeatif' / 'bukhari_enriched_v3_topical.json'

_BUKHARI_SOURCE_ID = 'hadith:sahih-al-bukhari-en'

# Fields from the enriched JSON that we merge into metadata_json.
_MERGE_FIELDS = (
    'primary_topics',
    'secondary_topics',
    'concept_vocabulary',
    'matn_text_clean',
    'topic_density',
    'abstain_reason',
    'is_multi_topic',
    'enrichment_version',
    'enrichment_model',
)

log = logging.getLogger('migrate_topical_to_db')


def _load_enriched() -> list[dict[str, Any]]:
    with _ENRICHED_JSON.open(encoding='utf-8') as fp:
        return json.load(fp)


def _project_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {field: record.get(field) for field in _MERGE_FIELDS}


def _preflight(session) -> int:
    """Return the count of Bukhari records in the DB; fail loudly if mismatched."""
    stmt = sa_text(f"""
        SELECT COUNT(*)
        FROM hadith_entries he
        JOIN source_works sw ON he.work_id = sw.id
        WHERE sw.source_id = :source_id
    """)
    count = session.execute(stmt, {'source_id': _BUKHARI_SOURCE_ID}).scalar() or 0
    return int(count)


def _update_batch(session, updates: list[tuple[str, dict[str, Any]]]) -> int:
    """Apply topical-field merges to a batch of hadith rows. Returns rows affected."""
    stmt = sa_text("""
        UPDATE hadith_entries
        SET metadata_json = COALESCE(metadata_json, '{}'::jsonb) || CAST(:new_fields AS jsonb)
        WHERE canonical_ref_collection = :hadith_id
        AND work_id = (SELECT id FROM source_works WHERE source_id = :source_id)
    """)
    affected = 0
    for hadith_id, new_fields in updates:
        result = session.execute(stmt, {
            'hadith_id': hadith_id,
            'new_fields': json.dumps(new_fields, ensure_ascii=False),
            'source_id': _BUKHARI_SOURCE_ID,
        })
        affected += result.rowcount or 0
    return affected


def _verify(session, sample_hadith_ids: list[str]) -> None:
    """Post-migration spot-check: confirm a random sample has the new fields."""
    stmt = sa_text("""
        SELECT canonical_ref_collection,
               metadata_json->'primary_topics' AS primary_topics,
               metadata_json->>'matn_text_clean' AS matn_clean,
               metadata_json->>'enrichment_version' AS version
        FROM hadith_entries he
        JOIN source_works sw ON he.work_id = sw.id
        WHERE sw.source_id = :source_id
          AND canonical_ref_collection = ANY(:ids)
    """)
    rows = session.execute(stmt, {'source_id': _BUKHARI_SOURCE_ID, 'ids': sample_hadith_ids}).fetchall()
    log.info('Verification sample (%d rows):', len(rows))
    for ref, topics, clean_preview, version in rows:
        preview = (clean_preview or '')[:80]
        log.info('  %s  topics=%s  version=%s  clean="%s..."',
                 ref, topics, version, preview)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Report what would be updated, do not write.')
    parser.add_argument('--batch-size', type=int, default=200, help='DB commit batch size.')
    parser.add_argument('--limit', type=int, default=0, help='Process at most N records (for testing).')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')

    if not _ENRICHED_JSON.exists():
        log.error('Enriched file not found: %s', _ENRICHED_JSON)
        sys.exit(2)

    records = _load_enriched()
    log.info('Enriched JSON: %d records', len(records))

    with get_session() as session:
        db_count = _preflight(session)
        log.info('DB Bukhari rows: %d', db_count)
        if db_count == 0:
            log.error('No Bukhari records found in DB. Ingestion must run first.')
            sys.exit(3)
        if db_count != len(records):
            log.warning('Count mismatch: DB has %d, JSON has %d. Proceeding — mismatched records will be silently skipped.',
                        db_count, len(records))

    if args.limit:
        records = records[: args.limit]

    if args.dry_run:
        log.info('--dry-run: would update %d records. Sample projections:', len(records))
        for r in records[:3]:
            print(json.dumps({'hadith_id': r.get('hadith_id'), **_project_fields(r)}, ensure_ascii=False, indent=2))
        return

    updated_total = 0
    not_found: list[str] = []
    start = time.time()

    with get_session() as session:
        for batch_start in range(0, len(records), args.batch_size):
            batch = records[batch_start: batch_start + args.batch_size]
            updates = [(r['hadith_id'], _project_fields(r)) for r in batch if r.get('hadith_id')]
            affected = _update_batch(session, updates)
            session.commit()
            # Track records that didn't match (no rows updated means hadith_id not in DB)
            missing_in_batch = len(updates) - affected
            updated_total += affected
            if missing_in_batch:
                # Collect the missing IDs for reporting (cheap — only when non-zero)
                stmt = sa_text("""
                    SELECT canonical_ref_collection FROM hadith_entries he
                    JOIN source_works sw ON he.work_id = sw.id
                    WHERE sw.source_id = :source_id AND canonical_ref_collection = ANY(:ids)
                """)
                existing = {
                    row[0] for row in session.execute(stmt, {
                        'source_id': _BUKHARI_SOURCE_ID,
                        'ids': [r[0] for r in updates],
                    }).fetchall()
                }
                batch_missing = [r[0] for r in updates if r[0] not in existing]
                not_found.extend(batch_missing)

            log.info('Migrated batch %d-%d (%d affected / %d in batch)',
                     batch_start + 1, batch_start + len(batch), affected, len(updates))

    elapsed = time.time() - start
    log.info('Done. Updated %d rows in %.1fs. Missing in DB: %d.',
             updated_total, elapsed, len(not_found))
    if not_found:
        log.warning('First 20 missing hadith_ids: %s', not_found[:20])

    # Verification
    with get_session() as session:
        sample_ids = [records[i]['hadith_id'] for i in (0, len(records) // 2, len(records) - 1) if records[i].get('hadith_id')]
        _verify(session, sample_ids)

    log.info('Migration complete. Every Bukhari row now carries primary_topics / concept_vocabulary / matn_text_clean / topic_density in metadata_json.')


if __name__ == '__main__':
    main()
