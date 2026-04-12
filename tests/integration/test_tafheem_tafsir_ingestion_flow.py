from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from tests.support.sqlite_shared import create_shared_sqlite_memory_engine

from domains.tafsir.repositories.tafsir_repository import SqlAlchemyTafsirRepository
from infrastructure.db.base import Base
from infrastructure.db.models.source_work import SourceWorkORM
from infrastructure.db.models.tafsir_section import TafsirSectionORM
from pipelines.ingestion.external.ingest_tafheem_al_quran import main as ingest_tafheem_main


@pytest.mark.parametrize("enable_source", [True])
def test_tafheem_ingestion_pipeline_writes_source_work_and_sections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enable_source: bool) -> None:
    engine = create_shared_sqlite_memory_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    source_file = tmp_path / "tafheem.json"
    source_file.write_text(
        json.dumps(
            {
                "1:1": {"t": "All praise be to Allah[[note]]"},
                "1:2": {"t": "The Lord of the Universe"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    @contextmanager
    def _fake_get_session(database_url: str | None = None, *, echo: bool = False):
        with SessionLocal() as session:
            yield session
            session.commit()

    monkeypatch.setattr("domains.tafsir.ingestion.ingest_pre_normalized.get_session", _fake_get_session)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ingest_tafheem_al_quran",
            "--source-file",
            str(source_file),
            "--enable-source",
            "--supports-quran-composition",
        ],
    )

    ingest_tafheem_main()

    with SessionLocal() as session:
        work = session.execute(select(SourceWorkORM).where(SourceWorkORM.source_id == "tafsir:tafheem-al-quran-en")).scalar_one()
        sections = session.execute(
            select(TafsirSectionORM).where(TafsirSectionORM.work_id == work.id).order_by(TafsirSectionORM.anchor_verse_key)
        ).scalars().all()

        assert work.display_name == "Tafheem al-Quran"
        assert work.enabled is True
        assert work.supports_quran_composition is True
        assert len(sections) == 2
        assert sections[0].anchor_verse_key == "1:1"
        assert sections[0].text_plain == 'On "All praise be to Allah": note'
        assert sections[0].raw_json["display_text"] == "All praise be to Allah"
        assert sections[0].raw_json["inline_note_count"] == 1
