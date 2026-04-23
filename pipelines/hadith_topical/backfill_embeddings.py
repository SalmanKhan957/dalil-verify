"""Backfill or regenerate matn embeddings for Bukhari hadith via OpenAI.

This script supports two source fields to embed:

    --source-field matn_text        (default — embeds raw English matn)
    --source-field matn_text_clean  (embeds narrator-stripped text from metadata_json)

The clean-text mode requires Phase 2 Step 1 (migrate_topical_to_db) to have run,
which populates `metadata_json.matn_text_clean` for every Bukhari row.

By default, records that already have a `matn_embedding` are skipped (resume-safe).
Pass `--overwrite` to regenerate every record — for example, after switching
the source field from matn_text to matn_text_clean.

Usage:
    python -m pipelines.hadith_topical.backfill_embeddings
    python -m pipelines.hadith_topical.backfill_embeddings --source-field matn_text_clean --overwrite
    python -m pipelines.hadith_topical.backfill_embeddings --source-field matn_text_clean --overwrite --batch-size 50
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy import text as sa_text

from infrastructure.config.settings import settings
from infrastructure.db.session import get_session

log = logging.getLogger('backfill_embeddings')

_EMBEDDING_MODEL = 'text-embedding-3-small'
_EMBEDDING_DIM = 1536
_BUKHARI_SOURCE_ID = 'hadith:sahih-al-bukhari-en'

_DEFAULT_BATCH_SIZE = 50
_DEFAULT_INTER_BATCH_DELAY_MS = 200
_MAX_RETRIES = 10
_MAX_BACKOFF_SECONDS = 60.0

_VALID_SOURCE_FIELDS = ('matn_text', 'matn_text_clean')


# ---------------------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------------------

def _embed_batch_with_retry(texts: list[str], max_retries: int = _MAX_RETRIES) -> list[list[float]] | None:
    if not settings.openai_api_key.strip():
        log.error('OPENAI_API_KEY is missing from settings.')
        return None

    payload = {
        'model': _EMBEDDING_MODEL,
        'input': [t.replace('\n', ' ') for t in texts],
        'dimensions': _EMBEDDING_DIM,
    }
    body = json.dumps(payload).encode('utf-8')

    for attempt in range(max_retries):
        req = urllib.request.Request(
            'https://api.openai.com/v1/embeddings',
            data=body,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {settings.openai_api_key}',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=60.0) as response:
                res_payload = json.loads(response.read().decode('utf-8'))
                data = sorted(res_payload.get('data', []), key=lambda x: x['index'])
                return [item['embedding'] for item in data]
        except urllib.error.HTTPError as exc:
            status = exc.code
            retry_after = exc.headers.get('Retry-After') if exc.headers else None
            if status in (429, 500, 502, 503, 504):
                try:
                    header_backoff = float(retry_after) if retry_after else 0.0
                except (TypeError, ValueError):
                    header_backoff = 0.0
                backoff = max(header_backoff, min(_MAX_BACKOFF_SECONDS, 2 ** attempt))
                log.warning('HTTP %s on attempt %d/%d; retrying in %.1fs', status, attempt + 1, max_retries, backoff)
                time.sleep(backoff)
                continue
            log.error('Non-retryable HTTP %s: %s', status, exc.read().decode('utf-8', errors='replace')[:400])
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            backoff = min(_MAX_BACKOFF_SECONDS / 2, 2 ** attempt)
            log.warning('Transient error on attempt %d/%d: %s; retrying in %.1fs', attempt + 1, max_retries, exc, backoff)
            time.sleep(backoff)
            continue
    log.error('Exhausted retries for embedding batch of %d records.', len(texts))
    return None


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------

def _fetch_records_to_embed(
    session,
    source_field: str,
    overwrite: bool,
) -> list[tuple[int, str, dict[str, Any]]]:
    """Return (row_id, source_text, current_metadata) for each record needing work."""
    if source_field == 'matn_text':
        text_expr = 'he.english_text'
    elif source_field == 'matn_text_clean':
        text_expr = "he.metadata_json->>'matn_text_clean'"
    else:
        raise ValueError(f'Unknown source_field: {source_field}')

    if overwrite:
        where_extra = ''
    else:
        where_extra = " AND (he.metadata_json->>'matn_embedding' IS NULL)"

    stmt = sa_text(f"""
        SELECT he.id,
               {text_expr} AS source_text,
               he.metadata_json
        FROM hadith_entries he
        JOIN source_works sw ON he.work_id = sw.id
        WHERE sw.source_id = :source_id
          AND {text_expr} IS NOT NULL
          {where_extra}
        ORDER BY he.id ASC
    """)
    rows = session.execute(stmt, {'source_id': _BUKHARI_SOURCE_ID}).fetchall()
    return [(int(r[0]), str(r[1] or ''), dict(r[2]) if r[2] else {}) for r in rows]


def _update_embeddings(session, rows: list[tuple[int, dict[str, Any]]]) -> None:
    stmt = sa_text("""
        UPDATE hadith_entries
        SET metadata_json = CAST(:meta AS jsonb)
        WHERE id = :id
    """)
    for entry_id, meta in rows:
        session.execute(stmt, {'meta': json.dumps(meta), 'id': entry_id})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-field', choices=_VALID_SOURCE_FIELDS, default='matn_text',
                        help='Which text field to embed.')
    parser.add_argument('--overwrite', action='store_true',
                        help='Regenerate even for records that already have a matn_embedding.')
    parser.add_argument('--batch-size', type=int, default=_DEFAULT_BATCH_SIZE,
                        help='OpenAI batch size (max 2048; pick smaller for tight rate limits).')
    parser.add_argument('--inter-batch-delay-ms', type=int, default=_DEFAULT_INTER_BATCH_DELAY_MS,
                        help='Sleep between batches in milliseconds. Raise if you see 429s.')
    parser.add_argument('--limit', type=int, default=0,
                        help='Stop after N records (testing).')
    parser.add_argument('--max-retries', type=int, default=_MAX_RETRIES,
                        help='Retries per batch on transient failures.')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')

    log.info('Source field: %s  |  overwrite: %s  |  batch_size: %d  |  inter_batch_delay_ms: %d',
             args.source_field, args.overwrite, args.batch_size, args.inter_batch_delay_ms)

    with get_session() as session:
        rows = _fetch_records_to_embed(session, args.source_field, args.overwrite)

    if args.limit:
        rows = rows[: args.limit]

    if not rows:
        log.info('Nothing to embed. All records already have a matn_embedding (or none match the source-field).')
        return

    log.info('Fetched %d records needing embeddings.', len(rows))

    processed = 0
    failed = 0
    start = time.time()
    delay = max(0, args.inter_batch_delay_ms) / 1000.0

    with get_session() as session:
        for batch_start in range(0, len(rows), args.batch_size):
            batch = rows[batch_start: batch_start + args.batch_size]
            ids = [r[0] for r in batch]
            texts = [r[1] for r in batch]
            metas = [dict(r[2]) for r in batch]

            embeddings = _embed_batch_with_retry(texts, max_retries=args.max_retries)
            if not embeddings:
                log.error('Embedding batch failed after retries; skipping IDs %d-%d.', ids[0], ids[-1])
                failed += len(batch)
                time.sleep(delay)
                continue
            if len(embeddings) != len(batch):
                log.error('Embedding count mismatch (got %d, expected %d); skipping batch.',
                          len(embeddings), len(batch))
                failed += len(batch)
                time.sleep(delay)
                continue

            updates = []
            for idx, entry_id in enumerate(ids):
                meta = metas[idx]
                meta['matn_embedding'] = embeddings[idx]
                meta['matn_embedding_source_field'] = args.source_field
                meta['matn_embedding_model'] = _EMBEDDING_MODEL
                updates.append((entry_id, meta))
            _update_embeddings(session, updates)
            session.commit()

            processed += len(batch)
            elapsed = time.time() - start
            rate = processed / elapsed if elapsed > 0 else 0
            log.info('[%d/%d]  elapsed=%.0fs  rate=%.1f/s  last_id=%d',
                     processed, len(rows), elapsed, rate, ids[-1])
            if delay > 0:
                time.sleep(delay)

    log.info('Done. Processed: %d  Failed: %d  Elapsed: %.1fs', processed, failed, time.time() - start)


if __name__ == '__main__':
    main()
