from __future__ import annotations

import argparse
import json

from domains.hadith.ingestion.ingest_collection import build_default_bukhari_meeatif_ingestion_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Ingest the MeeAtif Sahih al-Bukhari dataset into DALIL canonical Hadith storage.'
    )
    parser.add_argument(
        '--source-file',
        default='data/raw/hadith/meeatif/Sahih al-Bukhari.json',
        help='Path to the downloaded MeeAtif Sahih al-Bukhari JSON file.',
    )
    parser.add_argument(
        '--database-url',
        default=None,
        help='Optional DATABASE_URL override. If omitted, DALIL will use the shell env var.',
    )
    parser.add_argument(
        '--replace-existing',
        action='store_true',
        help='Delete existing rows for hadith:sahih-al-bukhari-en before ingesting the MeeAtif cutover.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service = build_default_bukhari_meeatif_ingestion_service(
        database_url=args.database_url,
        replace_existing_work_data=args.replace_existing,
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
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
