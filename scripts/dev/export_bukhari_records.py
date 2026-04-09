from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.engine import Engine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Export canonical Bukhari hadith records for topical indexing.')
    parser.add_argument('--output', default=r'.\tmp\hadith_records.json', help='Path to write exported records JSON.')
    parser.add_argument('--limit', type=int, default=None, help='Optional max number of rows to export for smoke testing.')
    parser.add_argument('--collection-source-id', default='hadith:sahih-al-bukhari-en', help='Collection source id to stamp into exported records.')
    parser.add_argument('--collection-slug', default='sahih-al-bukhari-en', help='Collection slug to stamp into exported records.')
    parser.add_argument('--schema', default='public', help='DB schema name. Defaults to public.')
    return parser.parse_args()


def get_engine() -> Engine:
    database_url = os.getenv('DATABASE_URL') or os.getenv('DALIL_DATABASE_URL')
    if not database_url:
        raise SystemExit('Neither DATABASE_URL nor DALIL_DATABASE_URL is set in this shell session.')
    return create_engine(database_url)


def main() -> int:
    args = parse_args()
    engine = get_engine()

    metadata = MetaData(schema=args.schema)
    source_works = Table('source_works', metadata, autoload_with=engine)
    hadith_entries = Table('hadith_entries', metadata, autoload_with=engine)
    hadith_books = Table('hadith_books', metadata, autoload_with=engine)
    hadith_chapters = Table('hadith_chapters', metadata, autoload_with=engine)

    work_id_subquery = select(source_works.c.id).where(source_works.c.source_id == args.collection_source_id).scalar_subquery()

    stmt = (
        select(
            hadith_entries.c.canonical_ref_collection.label('canonical_ref'),
            hadith_entries.c.collection_hadith_number,
            hadith_entries.c.in_book_hadith_number,
            hadith_entries.c.english_narrator,
            hadith_entries.c.english_text,
            hadith_entries.c.arabic_text,
            hadith_entries.c.metadata_json.label('entry_metadata_json'),
            hadith_books.c.book_number,
            hadith_books.c.title_en.label('book_title_en'),
            hadith_chapters.c.chapter_number,
            hadith_chapters.c.title_en.label('chapter_title_en'),
        )
        .select_from(
            hadith_entries.join(hadith_books, hadith_entries.c.book_id == hadith_books.c.id).join(
                hadith_chapters, hadith_entries.c.chapter_id == hadith_chapters.c.id
            )
        )
        .where(hadith_entries.c.work_id == work_id_subquery)
        .order_by(hadith_entries.c.collection_hadith_number.asc())
    )

    if args.limit is not None:
        stmt = stmt.limit(args.limit)

    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()

    records = []
    for row in rows:
        metadata_json = dict(row.get('entry_metadata_json') or {})
        records.append(
            {
                'canonical_ref': row['canonical_ref'],
                'collection_source_id': args.collection_source_id,
                'collection_slug': args.collection_slug,
                'collection_hadith_number': row['collection_hadith_number'],
                'book_number': row['book_number'],
                'chapter_number': row['chapter_number'],
                'numbering_quality': metadata_json.get('numbering_quality', 'collection_number_stable'),
                'english_text': row['english_text'],
                'arabic_text': row['arabic_text'],
                'english_narrator': row['english_narrator'],
                'book_title_en': row['book_title_en'],
                'chapter_title_en': row['chapter_title_en'],
                'in_book_hadith_number': row['in_book_hadith_number'],
                'reference_url': metadata_json.get('reference_url'),
                'in_book_reference_text': metadata_json.get('in_book_reference_text'),
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'Exported {len(records)} records -> {output_path}')
    print(f'Schema: {args.schema}')
    print(f'Collection source id: {args.collection_source_id}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
