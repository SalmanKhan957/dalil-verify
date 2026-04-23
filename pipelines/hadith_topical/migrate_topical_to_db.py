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

# ID format bridge:
#     JSON enriched file uses sunnah.com short form:  "bukhari:123"
#     DB canonical_ref_collection uses full form:     "hadith:sahih-al-bukhari-en:123"
# All downstream work (index, runtime, smoke tests) uses the DB/long form.
def _to_db_ref(json_hadith_id: str) -> str:
    """Translate 'bukhari:N' to 'hadith:sahih-al-bukhari-en:N'."""
    jid = (json_hadith_id or '').strip()
    if not jid:
        return jid
    if jid.startswith('hadith:sahih-al-bukhari-en:'):
        return jid
    if jid.startswith('bukhari:'):
        return f'hadith:sahih-al-bukhari-en:{jid.split(":", 1)[1]}'
    return jid


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


def _resolve_work_id(session) -> int | None:
    """Return the `source_works.id` for Bukhari or None if not found."""
    stmt = sa_text("SELECT id FROM source_works WHERE source_id = :source_id")
    row = session.execute(stmt, {'source_id': _BUKHARI_SOURCE_ID}).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def _preflight(session) -> dict[str, Any]:
    """Probe the DB so we fail loudly before doing anything destructive.

    Returns a diagnostic dict covering:
        - whether the Bukhari source_works row exists
        - how many hadith_entries rows are scoped to that work
        - a sample of canonical_ref_collection values for format confirmation
    """
    work_id = _resolve_work_id(session)
    diag: dict[str, Any] = {'work_id': work_id, 'total': 0, 'sample_refs': [], 'null_refs': 0}
    if work_id is None:
        return diag

    stmt_count = sa_text("""
        SELECT COUNT(*) FROM hadith_entries he WHERE he.work_id = :work_id
    """)
    diag['total'] = int(session.execute(stmt_count, {'work_id': work_id}).scalar() or 0)

    stmt_null = sa_text("""
        SELECT COUNT(*) FROM hadith_entries he
        WHERE he.work_id = :work_id AND he.canonical_ref_collection IS NULL
    """)
    diag['null_refs'] = int(session.execute(stmt_null, {'work_id': work_id}).scalar() or 0)

    stmt_sample = sa_text("""
        SELECT he.canonical_ref_collection
        FROM hadith_entries he
        WHERE he.work_id = :work_id AND he.canonical_ref_collection IS NOT NULL
        ORDER BY he.id
        LIMIT 5
    """)
    diag['sample_refs'] = [row[0] for row in session.execute(stmt_sample, {'work_id': work_id}).fetchall()]
    return diag


def _update_batch(session, work_id: int, updates: list[tuple[str, dict[str, Any]]]) -> int:
    """Apply topical-field merges to a batch of hadith rows. Returns rows affected."""
    stmt = sa_text("""
        UPDATE hadith_entries
        SET metadata_json = COALESCE(metadata_json, '{}'::jsonb) || CAST(:new_fields AS jsonb)
        WHERE canonical_ref_collection = :hadith_id
          AND work_id = :work_id
    """)
    affected = 0
    for hadith_id, new_fields in updates:
        result = session.execute(stmt, {
            'hadith_id': hadith_id,
            'new_fields': json.dumps(new_fields, ensure_ascii=False),
            'work_id': work_id,
        })
        affected += result.rowcount or 0
    return affected


def _verify(session, work_id: int, sample_hadith_ids: list[str]) -> None:
    """Post-migration spot-check: confirm a random sample has the new fields."""
    stmt = sa_text("""
        SELECT he.canonical_ref_collection,
               he.metadata_json->'primary_topics' AS primary_topics,
               he.metadata_json->>'matn_text_clean' AS matn_clean,
               he.metadata_json->>'enrichment_version' AS version
        FROM hadith_entries he
        WHERE he.work_id = :work_id
          AND he.canonical_ref_collection = ANY(:ids)
    """)
    rows = session.execute(stmt, {'work_id': work_id, 'ids': sample_hadith_ids}).fetchall()
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
        diag = _preflight(session)
    log.info('DB preflight: work_id=%s, total_rows=%d, null_refs=%d, sample_refs=%s',
             diag['work_id'], diag['total'], diag['null_refs'], diag['sample_refs'])

    work_id = diag['work_id']
    if work_id is None:
        log.error('No source_works row for source_id=%s. Bukhari ingestion has not run. Aborting.', _BUKHARI_SOURCE_ID)
        sys.exit(3)
    if diag['total'] == 0:
        log.error('source_works row exists but 0 hadith_entries are attached to work_id=%d.', work_id)
        sys.exit(3)
    if not diag['sample_refs']:
        log.error('All canonical_ref_collection values are NULL; cannot migrate by hadith_id.')
        sys.exit(3)

    # Cross-check format: does the JSON hadith_id match the DB ref format?
    json_first = records[0].get('hadith_id') if records else None
    db_first = diag['sample_refs'][0]
    if json_first and db_first and json_first != db_first:
        log.warning('Format sample: JSON first hadith_id=%r  vs  DB first canonical_ref=%r', json_first, db_first)
        # Only warn; the bulk of migration still proceeds and will report mismatches.

    if diag['total'] != len(records):
        log.warning('Count mismatch: DB has %d, JSON has %d. Unmatched records will be silently skipped.',
                    diag['total'], len(records))

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
            updates = [(_to_db_ref(r['hadith_id']), _project_fields(r)) for r in batch if r.get('hadith_id')]
            affected = _update_batch(session, work_id, updates)
            session.commit()
            missing_in_batch = len(updates) - affected
            updated_total += affected
            if missing_in_batch:
                stmt = sa_text("""
                    SELECT he.canonical_ref_collection FROM hadith_entries he
                    WHERE he.work_id = :work_id AND he.canonical_ref_collection = ANY(:ids)
                """)
                existing = {
                    row[0] for row in session.execute(stmt, {
                        'work_id': work_id,
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

    # Verification — query with DB-form refs
    with get_session() as session:
        sample_ids = [_to_db_ref(records[i]['hadith_id']) for i in (0, len(records) // 2, len(records) - 1) if records[i].get('hadith_id')]
        _verify(session, work_id, sample_ids)

    log.info('Migration complete. Every Bukhari row now carries primary_topics / concept_vocabulary / matn_text_clean / topic_density in metadata_json.')


if __name__ == '__main__':
    main()
