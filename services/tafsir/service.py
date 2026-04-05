from __future__ import annotations

from infrastructure.db.session import get_session
from domains.source_registry.registry import resolve_tafsir_source_for_explain
from domains.tafsir.overlap import TafsirOverlapService
from domains.tafsir.repositories.tafsir_repository import SqlAlchemyTafsirRepository
from domains.tafsir.types import TafsirOverlapHit, TafsirOverlapQuery, TafsirSourceWork


def is_source_enabled(source_id: str, *, database_url: str | None = None) -> bool:
    selected = resolve_tafsir_source_for_explain(source_id, database_url=database_url)
    return bool(selected and selected.enabled and selected.approved_for_answering)


class TafsirService:
    """Compatibility shim over the domains tafsir service surface.

    This module intentionally preserves patch points like ``get_session`` for
    older tests and legacy service-path consumers that monkeypatch symbols on
    ``services.tafsir.service`` directly.
    """

    def __init__(self, *, database_url: str | None = None) -> None:
        self.database_url = database_url

    def get_work_by_source_id(self, source_id: str) -> TafsirSourceWork:
        selected = resolve_tafsir_source_for_explain(source_id, database_url=self.database_url)
        if selected is None or not selected.enabled or not selected.approved_for_answering:
            raise PermissionError(f"tafsir_source_not_enabled: {source_id}")

        with get_session(database_url=self.database_url) as session:
            repository = SqlAlchemyTafsirRepository(session)
            work = repository.get_source_work_by_source_id(selected.source_id)
            if work is None:
                raise LookupError(f"tafsir_source_work_not_found_in_database: {selected.source_id}")
            return work

    def get_overlap_for_quran_span(
        self,
        *,
        source_id: str,
        surah_no: int,
        ayah_start: int,
        ayah_end: int,
        limit: int = 3,
    ) -> list[TafsirOverlapHit]:
        selected = resolve_tafsir_source_for_explain(source_id, database_url=self.database_url)
        if selected is None or not selected.enabled or not selected.approved_for_answering:
            raise PermissionError(f"tafsir_source_not_enabled: {source_id}")

        with get_session(database_url=self.database_url) as session:
            repository = SqlAlchemyTafsirRepository(session)
            work = repository.get_source_work_by_source_id(selected.source_id)
            if work is None:
                raise LookupError(f"tafsir_source_work_not_found_in_database: {selected.source_id}")

            overlap_service = TafsirOverlapService(repository)
            return overlap_service.fetch(
                TafsirOverlapQuery(
                    work_id=work.id,
                    surah_no=int(surah_no),
                    ayah_start=int(ayah_start),
                    ayah_end=int(ayah_end),
                    limit=int(limit),
                )
            )


__all__ = ["get_session", "is_source_enabled", "TafsirService"]
