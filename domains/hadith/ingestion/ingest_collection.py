from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

from domains.hadith.ingestion.normalizer import HadithCollectionNormalizer, HadithJsonMirrorNormalizerConfig
from infrastructure.db.models.hadith_book import HadithBookORM
from infrastructure.db.models.hadith_chapter import HadithChapterORM
from infrastructure.db.models.hadith_entry import HadithEntryORM
from infrastructure.db.models.hadith_grading import HadithGradingORM
from infrastructure.db.models.hadith_ingestion_run import HadithIngestionRunORM
from infrastructure.db.models.source_work import SourceWorkORM
from domains.hadith.repositories.hadith_repository import SqlAlchemyHadithRepository
from domains.hadith.types import HadithIngestionRunSummary
from infrastructure.db.session import get_session


class HadithCollectionIngestionService:
    def __init__(
        self,
        *,
        normalizer: Any | None = None,
        database_url: str | None = None,
        replace_existing_work_data: bool = False,
    ) -> None:
        self.normalizer = normalizer or HadithCollectionNormalizer()
        self.database_url = database_url
        self.replace_existing_work_data = replace_existing_work_data

    def ingest_file(self, source_file: str | Path) -> HadithIngestionRunSummary:
        source_path = Path(source_file)
        payload = json.loads(source_path.read_text(encoding='utf-8'))
        return self.ingest_payload(payload, source_root=source_path)

    def ingest_payload(self, payload: Any, *, source_root: str | Path = '<memory>') -> HadithIngestionRunSummary:
        batch = self.normalizer.normalize(payload)
        source_root_path = Path(source_root)

        with get_session(database_url=self.database_url) as session:
            repository = SqlAlchemyHadithRepository(session)
            collection = repository.upsert_collection(batch.collection_seed)
            if self.replace_existing_work_data:
                self._delete_existing_work_data(session=session, work_id=collection.id)
            run = repository.open_ingestion_run(work_id=collection.id, source_root=source_root_path, upstream_provider=batch.collection_seed.upstream_provider)

            book_id_by_number: dict[int, int] = {}
            chapter_id_by_key: dict[tuple[int, int], int] = {}
            inserted_count = 0
            updated_count = 0
            gradings_seen = 0

            for book in batch.books:
                book_record, op = repository.upsert_book(work_id=collection.id, book=book)
                book_id_by_number[book.book_number] = book_record.id
                inserted_count += int(op == 'inserted')
                updated_count += int(op == 'updated')

            for chapter in batch.chapters:
                book_id = book_id_by_number[chapter.book_number]
                chapter_record, op = repository.upsert_chapter(work_id=collection.id, book_id=book_id, chapter=chapter)
                chapter_id_by_key[(chapter.book_number, chapter.chapter_number)] = chapter_record.id
                inserted_count += int(op == 'inserted')
                updated_count += int(op == 'updated')

            for entry in batch.entries:
                book_id = book_id_by_number[entry.book_number]
                chapter_id = chapter_id_by_key.get((entry.book_number, entry.chapter_number)) if entry.chapter_number is not None else None
                _, op = repository.upsert_entry(work_id=collection.id, book_id=book_id, chapter_id=chapter_id, entry=entry)
                inserted_count += int(op == 'inserted')
                updated_count += int(op == 'updated')
                gradings_seen += int(entry.grading is not None)

            status = 'completed_with_warnings' if batch.notes else 'completed'
            notes_json = {
                'manifest': {
                    'collection_source_id': batch.manifest.collection_source_id,
                    'work_slug': batch.manifest.work_slug,
                    'language_code': batch.manifest.language_code,
                    'expected_books': batch.manifest.expected_books,
                    'expected_entries': batch.manifest.expected_entries,
                    'numbering_scheme': batch.manifest.numbering_scheme,
                    'replace_existing_work_data': self.replace_existing_work_data,
                },
                'notes': batch.notes,
            }

            repository.update_ingestion_run_counts(
                run_id=run.run_id,
                collections_seen=1,
                books_seen=len(batch.books),
                chapters_seen=len(batch.chapters),
                entries_seen=len(batch.entries),
                gradings_seen=gradings_seen,
                inserted_count=inserted_count,
                updated_count=updated_count,
                skipped_count=0,
                failed_count=0,
                notes_json=notes_json,
            )

            return repository.finalize_ingestion_run(run_id=run.run_id, status=status, notes_json=notes_json)

    @staticmethod
    def _delete_existing_work_data(*, session, work_id: int) -> None:
        entry_ids_subquery = select(HadithEntryORM.id).where(HadithEntryORM.work_id == work_id)
        session.execute(delete(HadithGradingORM).where(HadithGradingORM.entry_id.in_(entry_ids_subquery)))
        session.execute(delete(HadithEntryORM).where(HadithEntryORM.work_id == work_id))
        session.execute(delete(HadithChapterORM).where(HadithChapterORM.work_id == work_id))
        session.execute(delete(HadithBookORM).where(HadithBookORM.work_id == work_id))
        session.execute(delete(HadithIngestionRunORM).where(HadithIngestionRunORM.work_id == work_id))
        session.flush()


def build_default_bukhari_ingestion_service(*, database_url: str | None = None) -> HadithCollectionIngestionService:
    config = HadithJsonMirrorNormalizerConfig()
    return HadithCollectionIngestionService(
        normalizer=HadithCollectionNormalizer(config=config),
        database_url=database_url,
    )


def build_default_bukhari_meeatif_ingestion_service(
    *,
    database_url: str | None = None,
    replace_existing_work_data: bool = False,
) -> HadithCollectionIngestionService:
    from domains.hadith.ingestion.normalizer_meeatif import (
        MeeAtifHadithCollectionNormalizer,
        MeeAtifHadithNormalizerConfig,
    )

    config = MeeAtifHadithNormalizerConfig()
    return HadithCollectionIngestionService(
        normalizer=MeeAtifHadithCollectionNormalizer(config=config),
        database_url=database_url,
        replace_existing_work_data=replace_existing_work_data,
    )


def build_bukhari_enriched_v2_ingestion_service(
    *,
    database_url: str | None = None,
    replace_existing_work_data: bool = False,
    arabic_source_file: str | None = None,
) -> HadithCollectionIngestionService:
    from domains.hadith.ingestion.normalizer_meeatif_v2 import (
        MeeAtifEnrichedV2Normalizer,
        MeeAtifEnrichedV2NormalizerConfig,
    )

    config = MeeAtifEnrichedV2NormalizerConfig(arabic_source_file=arabic_source_file)
    return HadithCollectionIngestionService(
        normalizer=MeeAtifEnrichedV2Normalizer(config=config),
        database_url=database_url,
        replace_existing_work_data=replace_existing_work_data,
    )
