from __future__ import annotations

from pathlib import Path
from typing import Any

from infrastructure.db.session import get_session
from domains.tafsir.normalizer import normalize_resource_directory
from domains.tafsir.repositories.tafsir_repository import SqlAlchemyTafsirRepository
from domains.tafsir.types import SourceWorkSeed, TafsirIngestionChapterResult, TafsirIngestionRunSummary


def ingest_resource(
    *,
    source_dir: Path,
    resource_id: int,
    work_seed: SourceWorkSeed,
) -> TafsirIngestionRunSummary:
    """Normalize and ingest a raw Quran.Foundation tafsir snapshot into DALIL canonical storage."""
    normalized_sections = normalize_resource_directory(
        source_dir=source_dir,
        expected_resource_id=resource_id,
        source_id=work_seed.source_id,
        upstream_provider=work_seed.upstream_provider,
        language_code=work_seed.language_code,
    )

    with get_session() as session:
        repository = SqlAlchemyTafsirRepository(session)
        work = repository.upsert_source_work(work_seed)
        run = repository.open_ingestion_run(work_id=work.id, resource_id=resource_id, source_root=source_dir)

        notes: dict[str, Any] = {"work_slug": work.work_slug, "source_dir": str(source_dir.as_posix())}
        status = "completed"
        for chapter_number, sections in normalized_sections.items():
            warnings: list[str] = []
            counts = repository.bulk_upsert_tafsir_sections(work_id=work.id, sections=sections)
            result = TafsirIngestionChapterResult(
                chapter_number=chapter_number,
                raw_rows_seen=len({section.anchor_verse_key for section in sections})
                + sum(max(0, section.ayah_end - section.ayah_start) for section in sections),
                sections_built=len(sections),
                inserted_count=counts["inserted"],
                updated_count=counts["updated"],
                skipped_count=counts["skipped"],
                failed_count=0,
                warnings=warnings,
            )
            repository.record_chapter_result(run_id=run.run_id, result=result)

        return repository.finalize_ingestion_run(run_id=run.run_id, status=status, notes_json=notes)


__all__ = ["ingest_resource"]
