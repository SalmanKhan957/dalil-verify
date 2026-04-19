from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from domains.hadith.ingestion.ingest_collection import build_bukhari_enriched_v2_ingestion_service

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Ingest Bukhari Enriched V2 with Arabic text join.')
    parser.add_argument('--source-file', required=True, help='Path to bukhari_enriched_v2.json')
    parser.add_argument('--arabic-file', required=True, help='Path to Sahih al-Bukhari.json for join')
    parser.add_argument('--database-url', default=None, help='Override DALIL_DATABASE_URL for this run.')
    parser.add_argument('--replace', action='store_true', help='Replace existing work data')
    return parser

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = build_parser()
    args = parser.parse_args()
    
    service = build_bukhari_enriched_v2_ingestion_service(
        database_url=args.database_url,
        replace_existing_work_data=args.replace,
        arabic_source_file=args.arabic_file
    )
    summary = service.ingest_file(args.source_file)
    print(json.dumps({
        'run_id': summary.run_id,
        'status': summary.status,
        'collections_seen': summary.collections_seen,
        'books_seen': summary.books_seen,
        'chapters_seen': summary.chapters_seen,
        'entries_seen': summary.entries_seen,
        'gradings_seen': summary.gradings_seen,
        'inserted_count': summary.inserted_count,
        'updated_count': summary.updated_count,
        'skipped_count': summary.skipped_count,
        'failed_count': summary.failed_count,
        'notes_json': summary.notes_json,
    }, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
