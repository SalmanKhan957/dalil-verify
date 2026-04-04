from __future__ import annotations

from infrastructure.db.models.source_work import SourceWorkORM
from infrastructure.db.models.tafsir_ingestion_run import TafsirIngestionRunORM
from infrastructure.db.models.tafsir_section import TafsirSectionORM

__all__ = [
    "SourceWorkORM",
    "TafsirSectionORM",
    "TafsirIngestionRunORM",
]
