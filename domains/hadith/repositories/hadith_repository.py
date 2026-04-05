from __future__ import annotations

from pathlib import Path
from typing import Protocol

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from domains.hadith.contracts import HadithCitationReference
from domains.hadith.types import (
    HadithBookRecord,
    HadithChapterRecord,
    HadithCollectionRecord,
    HadithCollectionSeed,
    HadithEntryRecord,
    HadithGradingRecord,
    HadithIngestionRunOpened,
    HadithIngestionRunSummary,
    NormalizedHadithBook,
    NormalizedHadithChapter,
    NormalizedHadithEntry,
)
from infrastructure.db.models.hadith_book import HadithBookORM
from infrastructure.db.models.hadith_chapter import HadithChapterORM
from infrastructure.db.models.hadith_entry import HadithEntryORM
from infrastructure.db.models.hadith_grading import HadithGradingORM
from infrastructure.db.models.hadith_ingestion_run import HadithIngestionRunORM
from infrastructure.db.models.source_work import SourceWorkORM


class HadithRepository(Protocol):
    def upsert_collection(self, seed: HadithCollectionSeed) -> HadithCollectionRecord: ...
    def get_collection_by_source_id(self, source_id: str) -> HadithCollectionRecord | None: ...
    def open_ingestion_run(self, *, work_id: int, source_root: Path, upstream_provider: str) -> HadithIngestionRunOpened: ...
    def finalize_ingestion_run(self, *, run_id: int, status: str, notes_json: dict) -> HadithIngestionRunSummary: ...
    def update_ingestion_run_counts(self, *, run_id: int, collections_seen: int, books_seen: int, chapters_seen: int, entries_seen: int, gradings_seen: int, inserted_count: int, updated_count: int, skipped_count: int, failed_count: int, notes_json: dict) -> None: ...
    def upsert_book(self, *, work_id: int, book: NormalizedHadithBook) -> tuple[HadithBookRecord, str]: ...
    def upsert_chapter(self, *, work_id: int, book_id: int, chapter: NormalizedHadithChapter) -> tuple[HadithChapterRecord, str]: ...
    def upsert_entry(self, *, work_id: int, book_id: int, chapter_id: int | None, entry: NormalizedHadithEntry) -> tuple[HadithEntryRecord, str]: ...
    def lookup_by_citation(self, *, citation: HadithCitationReference, source_id: str) -> HadithEntryRecord | None: ...


class SqlAlchemyHadithRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_collection(self, seed: HadithCollectionSeed) -> HadithCollectionRecord:
        existing = self.session.execute(
            select(SourceWorkORM).where(SourceWorkORM.source_id == seed.source_id)
        ).scalar_one_or_none()

        values = {
            'source_domain': seed.source_domain,
            'work_slug': seed.work_slug,
            'source_id': seed.source_id,
            'display_name': seed.display_name,
            'citation_label': seed.citation_label,
            'author_name': seed.author_name,
            'language_code': seed.language_code,
            'source_kind': seed.source_kind,
            'upstream_provider': seed.upstream_provider,
            'upstream_resource_id': seed.upstream_resource_id,
            'enabled': seed.enabled,
            'approved_for_answering': seed.approved_for_answering,
            'default_for_explain': seed.default_for_explain,
            'supports_quran_composition': seed.supports_quran_composition,
            'priority_rank': seed.priority_rank,
            'version_label': seed.version_label,
            'policy_note': seed.policy_note,
            'metadata_json': seed.metadata_json or {},
        }

        if existing is None:
            row = SourceWorkORM(**values)
            self.session.add(row)
            self.session.flush()
            return _to_collection_record(row)

        for key, value in values.items():
            setattr(existing, key, value)
        self.session.flush()
        return _to_collection_record(existing)

    def get_collection_by_source_id(self, source_id: str) -> HadithCollectionRecord | None:
        row = self.session.execute(select(SourceWorkORM).where(SourceWorkORM.source_id == source_id)).scalar_one_or_none()
        return _to_collection_record(row) if row else None

    def open_ingestion_run(self, *, work_id: int, source_root: Path, upstream_provider: str) -> HadithIngestionRunOpened:
        run = HadithIngestionRunORM(
            work_id=work_id,
            source_root=str(source_root.as_posix()),
            upstream_provider=upstream_provider,
            status='running',
            notes_json={},
        )
        self.session.add(run)
        self.session.flush()
        return HadithIngestionRunOpened(run_id=run.id, work_id=work_id, source_root=run.source_root, upstream_provider=upstream_provider)

    def finalize_ingestion_run(self, *, run_id: int, status: str, notes_json: dict) -> HadithIngestionRunSummary:
        run = self._get_run(run_id)
        run.status = status
        run.notes_json = dict(notes_json or {})
        self.session.flush()
        return _to_ingestion_summary(run)

    def update_ingestion_run_counts(
        self,
        *,
        run_id: int,
        collections_seen: int,
        books_seen: int,
        chapters_seen: int,
        entries_seen: int,
        gradings_seen: int,
        inserted_count: int,
        updated_count: int,
        skipped_count: int,
        failed_count: int,
        notes_json: dict,
    ) -> None:
        run = self._get_run(run_id)
        run.collections_seen = collections_seen
        run.books_seen = books_seen
        run.chapters_seen = chapters_seen
        run.entries_seen = entries_seen
        run.gradings_seen = gradings_seen
        run.inserted_count = inserted_count
        run.updated_count = updated_count
        run.skipped_count = skipped_count
        run.failed_count = failed_count
        run.notes_json = dict(notes_json or {})
        self.session.flush()

    def upsert_book(self, *, work_id: int, book: NormalizedHadithBook) -> tuple[HadithBookRecord, str]:
        row = self.session.execute(
            select(HadithBookORM).where(
                and_(HadithBookORM.work_id == work_id, HadithBookORM.book_number == book.book_number)
            )
        ).scalar_one_or_none()
        operation = 'updated'
        if row is None:
            row = HadithBookORM(
                work_id=work_id,
                canonical_book_id=book.canonical_book_id,
                book_number=book.book_number,
                upstream_book_id=book.upstream_book_id,
                title_en=book.title_en,
                title_ar=book.title_ar,
                metadata_json=book.metadata_json or {},
            )
            self.session.add(row)
            self.session.flush()
            operation = 'inserted'
        else:
            row.canonical_book_id = book.canonical_book_id
            row.upstream_book_id = book.upstream_book_id
            row.title_en = book.title_en
            row.title_ar = book.title_ar
            row.metadata_json = book.metadata_json or {}
            self.session.flush()
        return _to_book_record(row), operation

    def upsert_chapter(self, *, work_id: int, book_id: int, chapter: NormalizedHadithChapter) -> tuple[HadithChapterRecord, str]:
        row = self.session.execute(
            select(HadithChapterORM).where(
                and_(HadithChapterORM.work_id == work_id, HadithChapterORM.book_id == book_id, HadithChapterORM.chapter_number == chapter.chapter_number)
            )
        ).scalar_one_or_none()
        operation = 'updated'
        if row is None:
            row = HadithChapterORM(
                work_id=work_id,
                book_id=book_id,
                canonical_chapter_id=chapter.canonical_chapter_id,
                chapter_number=chapter.chapter_number,
                upstream_chapter_id=chapter.upstream_chapter_id,
                title_en=chapter.title_en,
                title_ar=chapter.title_ar,
                metadata_json=chapter.metadata_json or {},
            )
            self.session.add(row)
            self.session.flush()
            operation = 'inserted'
        else:
            row.canonical_chapter_id = chapter.canonical_chapter_id
            row.upstream_chapter_id = chapter.upstream_chapter_id
            row.title_en = chapter.title_en
            row.title_ar = chapter.title_ar
            row.metadata_json = chapter.metadata_json or {}
            self.session.flush()
        return _to_chapter_record(row), operation

    def upsert_entry(self, *, work_id: int, book_id: int, chapter_id: int | None, entry: NormalizedHadithEntry) -> tuple[HadithEntryRecord, str]:
        row = self.session.execute(
            select(HadithEntryORM).where(
                and_(HadithEntryORM.work_id == work_id, HadithEntryORM.collection_hadith_number == entry.collection_hadith_number)
            )
        ).scalar_one_or_none()
        operation = 'updated'
        if row is None:
            row = HadithEntryORM(
                work_id=work_id,
                book_id=book_id,
                chapter_id=chapter_id,
                canonical_entry_id=entry.canonical_entry_id,
                canonical_ref_collection=entry.canonical_ref_collection,
                canonical_ref_book_hadith=entry.canonical_ref_book_hadith,
                canonical_ref_book_chapter_hadith=entry.canonical_ref_book_chapter_hadith,
                collection_hadith_number=entry.collection_hadith_number,
                in_book_hadith_number=entry.in_book_hadith_number,
                upstream_entry_id=entry.upstream_entry_id,
                upstream_book_id=entry.upstream_book_id,
                upstream_chapter_id=entry.upstream_chapter_id,
                english_narrator=entry.english_narrator,
                english_text=entry.english_text,
                arabic_text=entry.arabic_text,
                narrator_chain_text=entry.narrator_chain_text,
                matn_text=entry.matn_text,
                metadata_json=entry.metadata_json or {},
                raw_json=entry.raw_json or {},
            )
            self.session.add(row)
            self.session.flush()
            operation = 'inserted'
        else:
            row.book_id = book_id
            row.chapter_id = chapter_id
            row.canonical_entry_id = entry.canonical_entry_id
            row.canonical_ref_collection = entry.canonical_ref_collection
            row.canonical_ref_book_hadith = entry.canonical_ref_book_hadith
            row.canonical_ref_book_chapter_hadith = entry.canonical_ref_book_chapter_hadith
            row.in_book_hadith_number = entry.in_book_hadith_number
            row.upstream_entry_id = entry.upstream_entry_id
            row.upstream_book_id = entry.upstream_book_id
            row.upstream_chapter_id = entry.upstream_chapter_id
            row.english_narrator = entry.english_narrator
            row.english_text = entry.english_text
            row.arabic_text = entry.arabic_text
            row.narrator_chain_text = entry.narrator_chain_text
            row.matn_text = entry.matn_text
            row.metadata_json = entry.metadata_json or {}
            row.raw_json = entry.raw_json or {}
            self.session.flush()

        if entry.grading is not None:
            grade_row = self.session.execute(select(HadithGradingORM).where(HadithGradingORM.entry_id == row.id)).scalar_one_or_none()
            if grade_row is None:
                grade_row = HadithGradingORM(
                    entry_id=row.id,
                    grade_label=entry.grading.grade_label.value,
                    grade_text=entry.grading.grade_text,
                    grader_name=entry.grading.grader_name,
                    provenance_note=entry.grading.provenance_note,
                    metadata_json=entry.grading.metadata_json or {},
                )
                self.session.add(grade_row)
                self.session.flush()
            else:
                grade_row.grade_label = entry.grading.grade_label.value
                grade_row.grade_text = entry.grading.grade_text
                grade_row.grader_name = entry.grading.grader_name
                grade_row.provenance_note = entry.grading.provenance_note
                grade_row.metadata_json = entry.grading.metadata_json or {}
                self.session.flush()

        return self._get_entry_by_id(row.id), operation

    def lookup_by_citation(self, *, citation: HadithCitationReference, source_id: str) -> HadithEntryRecord | None:
        work = self.session.execute(select(SourceWorkORM).where(SourceWorkORM.source_id == source_id)).scalar_one_or_none()
        if work is None:
            return None

        stmt = select(HadithEntryORM).where(HadithEntryORM.work_id == work.id)
        if citation.reference_type.value == 'collection_number' and citation.hadith_number is not None:
            stmt = stmt.where(HadithEntryORM.collection_hadith_number == int(citation.hadith_number))
        elif citation.reference_type.value == 'book_and_hadith' and citation.book_number is not None and citation.hadith_number is not None:
            book = self.session.execute(
                select(HadithBookORM).where(and_(HadithBookORM.work_id == work.id, HadithBookORM.book_number == citation.book_number))
            ).scalar_one_or_none()
            if book is None:
                return None
            stmt = stmt.where(and_(HadithEntryORM.book_id == book.id, HadithEntryORM.in_book_hadith_number == int(citation.hadith_number)))
        elif citation.reference_type.value == 'book_chapter_and_hadith' and citation.book_number is not None and citation.chapter_number is not None and citation.hadith_number is not None:
            chapter = self.session.execute(
                select(HadithChapterORM).join(HadithBookORM, HadithChapterORM.book_id == HadithBookORM.id).where(
                    and_(
                        HadithChapterORM.work_id == work.id,
                        HadithBookORM.book_number == citation.book_number,
                        HadithChapterORM.chapter_number == citation.chapter_number,
                    )
                )
            ).scalar_one_or_none()
            if chapter is None:
                return None
            stmt = stmt.where(and_(HadithEntryORM.chapter_id == chapter.id, HadithEntryORM.in_book_hadith_number == int(citation.hadith_number)))
        else:
            return None

        # Book-based citations in bootstrap mirror datasets are not always unique.
        # Prefer a deterministic best-effort match rather than raising MultipleResultsFound.
        stmt = stmt.order_by(HadithEntryORM.collection_hadith_number.asc(), HadithEntryORM.id.asc())
        row = self.session.execute(stmt).scalars().first()
        return self._get_entry_by_id(row.id) if row else None

    def _get_run(self, run_id: int) -> HadithIngestionRunORM:
        run = self.session.execute(select(HadithIngestionRunORM).where(HadithIngestionRunORM.id == run_id)).scalar_one_or_none()
        if run is None:
            raise LookupError(f'hadith_ingestion_run_not_found: {run_id}')
        return run

    def _get_entry_by_id(self, entry_id: int) -> HadithEntryRecord:
        row = self.session.execute(select(HadithEntryORM).where(HadithEntryORM.id == entry_id)).scalar_one()
        grade = self.session.execute(select(HadithGradingORM).where(HadithGradingORM.entry_id == row.id)).scalar_one_or_none()
        book = self.session.execute(select(HadithBookORM).where(HadithBookORM.id == row.book_id)).scalar_one()
        chapter_number = None
        if row.chapter_id is not None:
            chapter_number = self.session.execute(select(HadithChapterORM.chapter_number).where(HadithChapterORM.id == row.chapter_id)).scalar_one_or_none()
        work = self.session.execute(select(SourceWorkORM).where(SourceWorkORM.id == row.work_id)).scalar_one()
        return _to_entry_record(row, work.source_id, book.book_number, chapter_number, grade)


def _to_collection_record(row: SourceWorkORM) -> HadithCollectionRecord:
    return HadithCollectionRecord(
        id=row.id,
        source_domain=row.source_domain,
        work_slug=row.work_slug,
        source_id=row.source_id,
        display_name=row.display_name,
        citation_label=row.citation_label,
        author_name=row.author_name,
        language_code=row.language_code,
        source_kind=row.source_kind,
        upstream_provider=row.upstream_provider,
        upstream_resource_id=row.upstream_resource_id,
        enabled=bool(row.enabled),
        approved_for_answering=bool(row.approved_for_answering),
        default_for_explain=bool(getattr(row, 'default_for_explain', False)),
        supports_quran_composition=bool(getattr(row, 'supports_quran_composition', False)),
        priority_rank=int(getattr(row, 'priority_rank', 1000) or 1000),
        version_label=getattr(row, 'version_label', None),
        policy_note=getattr(row, 'policy_note', None),
        metadata_json=dict(row.metadata_json or {}),
    )


def _to_book_record(row: HadithBookORM) -> HadithBookRecord:
    return HadithBookRecord(
        id=row.id,
        work_id=row.work_id,
        canonical_book_id=row.canonical_book_id,
        book_number=row.book_number,
        upstream_book_id=row.upstream_book_id,
        title_en=row.title_en,
        title_ar=row.title_ar,
        metadata_json=dict(row.metadata_json or {}),
    )


def _to_chapter_record(row: HadithChapterORM) -> HadithChapterRecord:
    return HadithChapterRecord(
        id=row.id,
        work_id=row.work_id,
        book_id=row.book_id,
        canonical_chapter_id=row.canonical_chapter_id,
        chapter_number=row.chapter_number,
        upstream_chapter_id=row.upstream_chapter_id,
        title_en=row.title_en,
        title_ar=row.title_ar,
        metadata_json=dict(row.metadata_json or {}),
    )


def _to_grading_record(row: HadithGradingORM | None) -> HadithGradingRecord | None:
    if row is None:
        return None
    from domains.hadith.types import HadithGradeLabel

    return HadithGradingRecord(
        id=row.id,
        entry_id=row.entry_id,
        grade_label=HadithGradeLabel(row.grade_label),
        grade_text=row.grade_text,
        grader_name=row.grader_name,
        provenance_note=row.provenance_note,
        metadata_json=dict(row.metadata_json or {}),
    )


def _to_entry_record(
    row: HadithEntryORM,
    collection_source_id: str,
    book_number: int,
    chapter_number: int | None,
    grading_row: HadithGradingORM | None,
) -> HadithEntryRecord:
    return HadithEntryRecord(
        id=row.id,
        work_id=row.work_id,
        book_id=row.book_id,
        chapter_id=row.chapter_id,
        collection_source_id=collection_source_id,
        canonical_entry_id=row.canonical_entry_id,
        canonical_ref_collection=row.canonical_ref_collection,
        canonical_ref_book_hadith=row.canonical_ref_book_hadith,
        canonical_ref_book_chapter_hadith=row.canonical_ref_book_chapter_hadith,
        collection_hadith_number=row.collection_hadith_number,
        in_book_hadith_number=row.in_book_hadith_number,
        book_number=book_number,
        chapter_number=chapter_number,
        english_narrator=row.english_narrator,
        english_text=row.english_text,
        arabic_text=row.arabic_text,
        narrator_chain_text=row.narrator_chain_text,
        matn_text=row.matn_text,
        metadata_json=dict(row.metadata_json or {}),
        raw_json=dict(row.raw_json or {}),
        grading=_to_grading_record(grading_row),
    )


def _to_ingestion_summary(run: HadithIngestionRunORM) -> HadithIngestionRunSummary:
    return HadithIngestionRunSummary(
        run_id=run.id,
        status=run.status,
        collections_seen=run.collections_seen,
        books_seen=run.books_seen,
        chapters_seen=run.chapters_seen,
        entries_seen=run.entries_seen,
        gradings_seen=run.gradings_seen,
        inserted_count=run.inserted_count,
        updated_count=run.updated_count,
        skipped_count=run.skipped_count,
        failed_count=run.failed_count,
        notes_json=dict(run.notes_json or {}),
    )
