from __future__ import annotations

import argparse
import json

from pipelines.ingestion.hadith.ingest_collection import ingest_hadith_json_collection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Ingest a hadith-json style by-book collection into DALIL canonical tables.')
    parser.add_argument('--source-file', required=True, help='Path to the hadith-json book file, e.g. bukhari.json')
    parser.add_argument('--database-url', default=None, help='Override DALIL_DATABASE_URL for this run.')
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    summary = ingest_hadith_json_collection(source_file=args.source_file, database_url=args.database_url)
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
