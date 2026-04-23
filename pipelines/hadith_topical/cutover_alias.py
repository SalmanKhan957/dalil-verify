"""Bukhari topical alias cutover — point the runtime alias at a target index.

Runtime code imports `HADITH_BUKHARI_TOPICAL_INDEX` which resolves to the
alias `dalil-hadith-bukhari-topical`. This script atomically updates that
alias to point at a named index (defaults to v2). Use it for:

    * Initial cutover after building a new v2 index.
    * Future v3 / v4 rebuilds — build the new versioned index, run
      smoke_test.py against it, then cutover via this script.
    * Rollback — if v2 breaks in production, rerun with --target=v1
      (requires v1 index to still exist).

The cutover is performed as a single OpenSearch `_aliases` POST request
with both `remove` and `add` actions, which OpenSearch applies atomically.
No query sees a gap between the old and new index.

Usage:
    python -m pipelines.hadith_topical.cutover_alias             # dry-run
    python -m pipelines.hadith_topical.cutover_alias --execute   # real swap
    python -m pipelines.hadith_topical.cutover_alias --execute --target dalil-hadith-bukhari-topical-v3
    python -m pipelines.hadith_topical.cutover_alias --rollback  # point at v1
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from infrastructure.search.index_names import (
    HADITH_BUKHARI_TOPICAL_ALIAS,
    HADITH_BUKHARI_TOPICAL_INDEX_V1,
    HADITH_BUKHARI_TOPICAL_INDEX_V2,
)
from infrastructure.search.opensearch_client import OpenSearchClient

log = logging.getLogger('cutover_alias')


def _current_alias_target(client: OpenSearchClient) -> str | None:
    """Return the index the alias currently points at, or None if no alias."""
    resp = client._request(
        'GET',
        f'/_cat/aliases/{HADITH_BUKHARI_TOPICAL_ALIAS}?format=json',
        allow_404=True,
    )
    if not isinstance(resp, list):
        return None
    for entry in resp:
        if entry.get('alias') == HADITH_BUKHARI_TOPICAL_ALIAS:
            return entry.get('index')
    return None


def _index_exists(client: OpenSearchClient, index: str) -> bool:
    resp = client._request('HEAD', f'/{index}', allow_404=True)
    return (resp or {}).get('status_code') == 200


def _index_doc_count(client: OpenSearchClient, index: str) -> int | None:
    try:
        resp = client.search(index=index, body={'size': 0, 'query': {'match_all': {}}})
    except Exception:
        return None
    total = (((resp or {}).get('hits') or {}).get('total') or {})
    return int(total.get('value', 0)) if isinstance(total, dict) else None


def _verify_target(client: OpenSearchClient, target: str) -> bool:
    """Confirm target index exists and has a plausible doc count before cutover."""
    if not _index_exists(client, target):
        log.error('Target index %s does not exist. Build it first.', target)
        return False
    count = _index_doc_count(client, target)
    if count is None:
        log.error('Could not read doc count from %s.', target)
        return False
    log.info('Target %s has %d documents.', target, count)
    if count < 100:
        log.warning('Target has only %d documents. Expected thousands. Check before proceeding.', count)
        return False
    return True


def _swap_alias(
    client: OpenSearchClient,
    *,
    current: str | None,
    target: str,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    if current and current != target:
        actions.append({'remove': {'index': current, 'alias': HADITH_BUKHARI_TOPICAL_ALIAS}})
    actions.append({'add': {'index': target, 'alias': HADITH_BUKHARI_TOPICAL_ALIAS}})
    return client._request('POST', '/_aliases', json_body={'actions': actions})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', default=HADITH_BUKHARI_TOPICAL_INDEX_V2,
                        help=f'Index to point the alias at (default: {HADITH_BUKHARI_TOPICAL_INDEX_V2}).')
    parser.add_argument('--rollback', action='store_true',
                        help=f'Shortcut for --target {HADITH_BUKHARI_TOPICAL_INDEX_V1}.')
    parser.add_argument('--execute', action='store_true',
                        help='Actually perform the swap. Without this flag, prints a dry-run plan only.')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')

    if args.rollback:
        target = HADITH_BUKHARI_TOPICAL_INDEX_V1
    else:
        target = args.target

    client = OpenSearchClient.from_environment()
    if not client.is_enabled:
        log.error('OPENSEARCH_URL not set.')
        sys.exit(2)

    log.info('Alias: %s', HADITH_BUKHARI_TOPICAL_ALIAS)
    current = _current_alias_target(client)
    log.info('Current target: %s', current or '(none)')
    log.info('Requested target: %s', target)

    if current == target:
        log.info('Alias already points at %s. Nothing to do.', target)
        return

    if not _verify_target(client, target):
        log.error('Target verification failed. Aborting.')
        sys.exit(3)

    if not args.execute:
        log.info('--- Dry-run plan ---')
        if current:
            log.info('  REMOVE: alias=%s from index=%s', HADITH_BUKHARI_TOPICAL_ALIAS, current)
        log.info('  ADD:    alias=%s to index=%s', HADITH_BUKHARI_TOPICAL_ALIAS, target)
        log.info('Rerun with --execute to perform the swap.')
        return

    log.info('Executing atomic alias swap ...')
    resp = _swap_alias(client, current=current, target=target)
    log.info('Response: %s', resp)

    verify = _current_alias_target(client)
    if verify != target:
        log.error('Post-swap verification failed. Alias now points at: %s. Expected: %s.',
                  verify, target)
        sys.exit(4)
    log.info('Alias is now %s -> %s. Cutover complete.', HADITH_BUKHARI_TOPICAL_ALIAS, target)


if __name__ == '__main__':
    main()
