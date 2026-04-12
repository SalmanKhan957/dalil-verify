from __future__ import annotations

from pathlib import Path
from typing import Any

from infrastructure.db.session import get_session
from domains.tafsir.repositories.tafsir_repository import SqlAlchemyTafsirRepository
from domains.tafsir.types import NormalizedTafsirSection, TafsirIngestionChapterResult, TafsirIngestionRunSummary, SourceWorkSeed



def ingest_pre_normalized_sections(
    *,
    source_root: Path,
    resource_id: int,
    work_seed: SourceWorkSeed,
    normalized_sections: dict[int, list[NormalizedTafsirSection]],
) -> TafsirIngestionRunSummary:
    with get_session() as session:
        repository = SqlAlchemyTafsirRepository(session)
        work = repository.upsert_source_work(work_seed)
        run = repository.open_ingestion_run(work_id=work.id, resource_id=resource_id, source_root=source_root)

        notes: dict[str, Any] = {
            "work_slug": work.work_slug,
            "source_root": str(source_root.as_posix()),
            "normalized_provider": work_seed.upstream_provider,
        }
        status = "completed"

        for chapter_number, sections in sorted(normalized_sections.items()):
            counts = repository.bulk_upsert_tafsir_sections(work_id=work.id, sections=sections)
            result = TafsirIngestionChapterResult(
                chapter_number=chapter_number,
                raw_rows_seen=len(sections),
                sections_built=len(sections),
                inserted_count=counts["inserted"],
                updated_count=counts["updated"],
                skipped_count=counts["skipped"],
                failed_count=0,
                warnings=[],
            )
            repository.record_chapter_result(run_id=run.run_id, result=result)

        return repository.finalize_ingestion_run(run_id=run.run_id, status=status, notes_json=notes)


__all__ = ["ingest_pre_normalized_sections"]
