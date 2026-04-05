from __future__ import annotations

from pathlib import Path

from domains.hadith.ingestion.ingest_collection import build_default_bukhari_ingestion_service
from domains.hadith.types import HadithIngestionRunSummary


def ingest_hadith_json_collection(*, source_file: str | Path, database_url: str | None = None) -> HadithIngestionRunSummary:
    service = build_default_bukhari_ingestion_service(database_url=database_url)
    return service.ingest_file(source_file)
