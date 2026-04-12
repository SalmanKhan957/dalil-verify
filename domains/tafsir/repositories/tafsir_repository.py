from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from infrastructure.db.models.source_work import SourceWorkORM
from infrastructure.db.models.tafsir_ingestion_run import TafsirIngestionRunORM
from infrastructure.db.models.tafsir_section import TafsirSectionORM
from domains.tafsir.types import (
    NormalizedTafsirSection,
    SourceWorkSeed,
    TafsirIngestionChapterResult,
    TafsirIngestionRunOpened,
    TafsirIngestionRunSummary,
    TafsirOverlapHit,
    TafsirOverlapQuery,
    TafsirSourceWork,
)


class TafsirRepository(Protocol):
    def upsert_source_work(self, seed: SourceWorkSeed) -> TafsirSourceWork: ...

    def get_source_work_by_source_id(self, source_id: str) -> TafsirSourceWork | None: ...

    def get_source_work_by_work_slug(self, work_slug: str) -> TafsirSourceWork | None: ...

    def open_ingestion_run(self, *, work_id: int, resource_id: int, source_root: Path) -> TafsirIngestionRunOpened: ...

    def record_chapter_result(self, *, run_id: int, result: TafsirIngestionChapterResult) -> None: ...

    def finalize_ingestion_run(self, *, run_id: int, status: str, notes_json: dict) -> TafsirIngestionRunSummary: ...

    def upsert_tafsir_section(self, *, work_id: int, section: NormalizedTafsirSection) -> str: ...

    def bulk_upsert_tafsir_sections(
        self, *, work_id: int, sections: Sequence[NormalizedTafsirSection]
    ) -> dict[str, int]: ...

    def fetch_overlap_hits(self, query: TafsirOverlapQuery) -> list[TafsirOverlapHit]: ...


class SqlAlchemyTafsirRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_source_work(self, seed: SourceWorkSeed) -> TafsirSourceWork:
        existing = self.session.execute(
            select(SourceWorkORM).where(SourceWorkORM.source_id == seed.source_id)
        ).scalar_one_or_none()

        if existing is None:
            existing = SourceWorkORM(
                source_domain=seed.source_domain,
                work_slug=seed.work_slug,
                source_id=seed.source_id,
                display_name=seed.display_name,
                citation_label=seed.citation_label,
                author_name=seed.author_name,
                language_code=seed.language_code,
                source_kind=seed.source_kind,
                upstream_provider=seed.upstream_provider,
                upstream_resource_id=seed.upstream_resource_id,
                enabled=seed.enabled,
                approved_for_answering=seed.approved_for_answering,
                default_for_explain=seed.default_for_explain,
                supports_quran_composition=seed.supports_quran_composition,
                priority_rank=seed.priority_rank,
                version_label=seed.version_label,
                policy_note=seed.policy_note,
                metadata_json=seed.metadata_json or {},
            )
            self.session.add(existing)
            self.session.flush()
        else:
            existing.display_name = seed.display_name
            existing.citation_label = seed.citation_label
            existing.author_name = seed.author_name
            existing.enabled = seed.enabled
            existing.approved_for_answering = seed.approved_for_answering
            existing.default_for_explain = seed.default_for_explain
            existing.supports_quran_composition = seed.supports_quran_composition
            existing.priority_rank = seed.priority_rank
            existing.version_label = seed.version_label
            existing.policy_note = seed.policy_note
            existing.metadata_json = seed.metadata_json or {}
            self.session.flush()

        return _to_source_work(existing)

    def get_source_work_by_source_id(self, source_id: str) -> TafsirSourceWork | None:
        row = self.session.execute(
            select(SourceWorkORM).where(SourceWorkORM.source_id == source_id)
        ).scalar_one_or_none()
        return _to_source_work(row) if row else None

    def get_source_work_by_work_slug(self, work_slug: str) -> TafsirSourceWork | None:
        row = self.session.execute(
            select(SourceWorkORM).where(SourceWorkORM.work_slug == work_slug)
        ).scalar_one_or_none()
        return _to_source_work(row) if row else None

    def open_ingestion_run(self, *, work_id: int, resource_id: int, source_root: Path) -> TafsirIngestionRunOpened:
        run = TafsirIngestionRunORM(
            work_id=work_id,
            resource_id=resource_id,
            source_root=str(source_root.as_posix()),
            status="running",
            notes_json={},
        )
        self.session.add(run)
        self.session.flush()
        return TafsirIngestionRunOpened(
            run_id=run.id,
            work_id=work_id,
            resource_id=resource_id,
            source_root=run.source_root,
        )

    def record_chapter_result(self, *, run_id: int, result: TafsirIngestionChapterResult) -> None:
        run = self._get_run(run_id)
        notes = dict(run.notes_json or {})
        warnings = notes.setdefault("warnings", {})
        if result.warnings:
            warnings[str(result.chapter_number)] = result.warnings

        run.chapters_seen += result.chapters_seen if hasattr(result, 'chapters_seen') else 1
        run.raw_rows_seen += result.raw_rows_seen
        run.sections_built += result.sections_built
        run.inserted_count += result.inserted_count
        run.updated_count += result.updated_count
        run.skipped_count += result.skipped_count
        run.failed_count += result.failed_count
        run.notes_json = notes
        self.session.flush()

    def finalize_ingestion_run(self, *, run_id: int, status: str, notes_json: dict) -> TafsirIngestionRunSummary:
        run = self._get_run(run_id)
        run.status = status
        run.notes_json = dict(notes_json or {})
        self.session.flush()
        return _to_ingestion_summary(run)

    def upsert_tafsir_section(self, *, work_id: int, section: NormalizedTafsirSection) -> str:
        existing = self.session.execute(
            select(TafsirSectionORM).where(
                and_(
                    TafsirSectionORM.work_id == work_id,
                    TafsirSectionORM.upstream_entry_id == section.upstream_entry_id,
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            row = TafsirSectionORM(
                work_id=work_id,
                canonical_section_id=section.canonical_section_id,
                source_id=section.source_id,
                upstream_provider=section.upstream_provider,
                upstream_resource_id=section.upstream_resource_id,
                upstream_entry_id=section.upstream_entry_id,
                language_code=section.language_code,
                slug=section.slug,
                language_id=section.language_id,
                surah_no=section.surah_no,
                ayah_start=section.ayah_start,
                ayah_end=section.ayah_end,
                anchor_verse_key=section.anchor_verse_key,
                quran_span_ref=section.quran_span_ref,
                coverage_mode=section.coverage_mode,
                coverage_confidence=section.coverage_confidence,
                text_html=section.text_html,
                text_plain=section.text_plain,
                text_plain_normalized=section.text_plain_normalized,
                text_hash=section.text_hash,
                source_file_path=section.source_file_path,
                source_manifest_path=section.source_manifest_path,
                raw_json=section.raw_json,
            )
            self.session.add(row)
            self.session.flush()
            return "inserted"

        changed = False
        for field in (
            "ayah_start",
            "ayah_end",
            "anchor_verse_key",
            "quran_span_ref",
            "coverage_mode",
            "coverage_confidence",
            "text_html",
            "text_plain",
            "text_plain_normalized",
            "text_hash",
            "slug",
            "language_id",
            "source_file_path",
            "source_manifest_path",
            "raw_json",
        ):
            new_value = getattr(section, field)
            if getattr(existing, field) != new_value:
                setattr(existing, field, new_value)
                changed = True

        if changed:
            self.session.flush()
            return "updated"
        return "skipped"

    def bulk_upsert_tafsir_sections(
        self, *, work_id: int, sections: Sequence[NormalizedTafsirSection]
    ) -> dict[str, int]:
        counts = {"inserted": 0, "updated": 0, "skipped": 0}
        for section in sections:
            outcome = self.upsert_tafsir_section(work_id=work_id, section=section)
            counts[outcome] += 1
        return counts

    def fetch_overlap_hits(self, query: TafsirOverlapQuery) -> list[TafsirOverlapHit]:
        query_ayah_start = query.ayah_start
        query_ayah_end = query.ayah_end

        stmt = (
            select(
                TafsirSectionORM.id.label("section_id"),
                TafsirSectionORM.canonical_section_id,
                TafsirSectionORM.work_id,
                SourceWorkORM.source_id,
                SourceWorkORM.display_name,
                SourceWorkORM.citation_label,
                TafsirSectionORM.surah_no,
                TafsirSectionORM.ayah_start,
                TafsirSectionORM.ayah_end,
                TafsirSectionORM.anchor_verse_key,
                TafsirSectionORM.quran_span_ref,
                TafsirSectionORM.coverage_mode,
                TafsirSectionORM.coverage_confidence,
                TafsirSectionORM.text_plain,
                TafsirSectionORM.text_html,
                TafsirSectionORM.raw_json,
            )
            .join(SourceWorkORM, SourceWorkORM.id == TafsirSectionORM.work_id)
            .where(
                TafsirSectionORM.work_id == query.work_id,
                TafsirSectionORM.surah_no == query.surah_no,
                ~((TafsirSectionORM.ayah_end < query_ayah_start) | (TafsirSectionORM.ayah_start > query_ayah_end)),
            )
        )

        rows = self.session.execute(stmt).all()
        hits: list[TafsirOverlapHit] = []
        for row in rows:
            overlap_ayah_count = min(row.ayah_end, query_ayah_end) - max(row.ayah_start, query_ayah_start) + 1
            if overlap_ayah_count <= 0:
                continue

            anchor_distance = abs(_extract_ayah_from_verse_key(row.anchor_verse_key) - query_ayah_start)
            exact_span_match = row.ayah_start == query_ayah_start and row.ayah_end == query_ayah_end
            contains_query_span = row.ayah_start <= query_ayah_start and row.ayah_end >= query_ayah_end
            query_contains_section = query_ayah_start <= row.ayah_start and query_ayah_end >= row.ayah_end
            span_width = row.ayah_end - row.ayah_start + 1

            hits.append(
                TafsirOverlapHit(
                    section_id=row.section_id,
                    canonical_section_id=row.canonical_section_id,
                    work_id=row.work_id,
                    source_id=row.source_id,
                    display_name=row.display_name,
                    citation_label=row.citation_label,
                    surah_no=row.surah_no,
                    ayah_start=row.ayah_start,
                    ayah_end=row.ayah_end,
                    anchor_verse_key=row.anchor_verse_key,
                    quran_span_ref=row.quran_span_ref,
                    coverage_mode=row.coverage_mode,
                    coverage_confidence=float(row.coverage_confidence),
                    text_plain=row.text_plain,
                    text_html=row.text_html,
                    overlap_ayah_count=int(overlap_ayah_count),
                    exact_span_match=bool(exact_span_match),
                    contains_query_span=bool(contains_query_span),
                    query_contains_section=bool(query_contains_section),
                    span_width=int(span_width),
                    anchor_distance=int(anchor_distance),
                    raw_json=dict(row.raw_json or {}),
                )
            )
        return hits

    def _get_run(self, run_id: int) -> TafsirIngestionRunORM:
        run = self.session.execute(
            select(TafsirIngestionRunORM).where(TafsirIngestionRunORM.id == run_id)
        ).scalar_one_or_none()
        if run is None:  # pragma: no cover
            raise ValueError(f"Ingestion run {run_id} was not found.")
        return run


def _extract_ayah_from_verse_key(verse_key: str) -> int:
    try:
        _surah, ayah = verse_key.split(":", 1)
        return int(ayah)
    except (AttributeError, ValueError) as exc:  # pragma: no cover
        raise ValueError(f"Invalid verse_key for anchor distance calculation: {verse_key!r}") from exc


def _to_source_work(row: SourceWorkORM) -> TafsirSourceWork:
    return TafsirSourceWork(
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
        enabled=row.enabled,
        approved_for_answering=row.approved_for_answering,
        default_for_explain=bool(getattr(row, "default_for_explain", False)),
        supports_quran_composition=bool(getattr(row, "supports_quran_composition", False)),
        priority_rank=int(getattr(row, "priority_rank", 1000) or 1000),
        version_label=row.version_label,
        policy_note=getattr(row, "policy_note", None),
        metadata_json=row.metadata_json or {},
    )


def _to_ingestion_summary(run: TafsirIngestionRunORM) -> TafsirIngestionRunSummary:
    return TafsirIngestionRunSummary(
        run_id=run.id,
        status=run.status,
        chapters_seen=run.chapters_seen,
        raw_rows_seen=run.raw_rows_seen,
        sections_built=run.sections_built,
        inserted_count=run.inserted_count,
        updated_count=run.updated_count,
        skipped_count=run.skipped_count,
        failed_count=run.failed_count,
        notes_json=run.notes_json or {},
    )
