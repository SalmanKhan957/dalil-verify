from __future__ import annotations

import json
from pathlib import Path

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.db.base import Base
from services.tafsir.repository import SqlAlchemyTafsirRepository
from services.tafsir.types import SourceWorkSeed, TafsirIngestionChapterResult


def test_repository_upsert_and_ingestion_run_flow() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    with SessionLocal() as session:
        repository = SqlAlchemyTafsirRepository(session)
        work = repository.upsert_source_work(
            SourceWorkSeed(
                source_domain="tafsir",
                work_slug="ibn-kathir-en",
                source_id="tafsir:ibn-kathir-en",
                display_name="Tafsir Ibn Kathir (English)",
                citation_label="Tafsir Ibn Kathir",
                author_name="Ibn Kathir",
                language_code="en",
                source_kind="commentary",
                upstream_provider="quran_foundation",
                upstream_resource_id=169,
                enabled=False,
                approved_for_answering=False,
                version_label=None,
                metadata_json={},
            )
        )
        run = repository.open_ingestion_run(work_id=work.id, resource_id=169, source_root=Path("/tmp/resource_169"))
        repository.record_chapter_result(
            run_id=run.run_id,
            result=TafsirIngestionChapterResult(
                chapter_number=112,
                raw_rows_seen=4,
                sections_built=1,
                inserted_count=1,
                updated_count=0,
                skipped_count=0,
                failed_count=0,
                warnings=[],
            ),
        )
        summary = repository.finalize_ingestion_run(run_id=run.run_id, status="completed", notes_json={"ok": True})

        assert summary.chapters_seen == 1
        assert summary.inserted_count == 1
        assert summary.status == "completed"
