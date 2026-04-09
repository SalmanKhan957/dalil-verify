from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import and_, select

from domains.hadith.types import HadithEntryRecord
from domains.hadith.repositories.hadith_repository import SqlAlchemyHadithRepository
from infrastructure.db.models.hadith_entry import HadithEntryORM
from infrastructure.db.models.source_work import SourceWorkORM
from infrastructure.db.session import get_session


def hydrate_hadith_entries_by_collection_refs(
    canonical_refs: Iterable[str],
    *,
    collection_source_id: str | None = None,
    database_url: str | None = None,
) -> dict[str, HadithEntryRecord]:
    requested = [ref for ref in canonical_refs if ref]
    if not requested:
        return {}
    with get_session(database_url=database_url) as session:
        repository = SqlAlchemyHadithRepository(session)
        stmt = select(HadithEntryORM.id, HadithEntryORM.canonical_ref_collection).where(HadithEntryORM.canonical_ref_collection.in_(requested))
        if collection_source_id:
            stmt = stmt.join(SourceWorkORM, HadithEntryORM.work_id == SourceWorkORM.id).where(SourceWorkORM.source_id == collection_source_id)
        rows = session.execute(stmt).all()
        hydrated: dict[str, HadithEntryRecord] = {}
        for entry_id, canonical_ref in rows:
            hydrated[str(canonical_ref)] = repository._get_entry_by_id(int(entry_id))
        return hydrated
