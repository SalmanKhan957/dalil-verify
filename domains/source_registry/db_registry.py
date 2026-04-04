from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from infrastructure.db.models.source_work import SourceWorkORM
from infrastructure.db.session import get_session
from shared.schemas.source_record import SourceRecord


class SourceRegistryDatabaseError(RuntimeError):
    pass


def _to_source_record(row: SourceWorkORM) -> SourceRecord:
    return SourceRecord(
        source_id=row.source_id,
        source_domain=row.source_domain,
        source_kind=row.source_kind,
        display_name=row.display_name,
        citation_label=row.citation_label,
        language=row.language_code,
        enabled=bool(row.enabled),
        approved_for_answering=bool(row.approved_for_answering),
        default_for_explain=bool(getattr(row, "default_for_explain", False)),
        supports_quran_composition=bool(getattr(row, "supports_quran_composition", False)),
        priority_rank=int(getattr(row, "priority_rank", 1000) or 1000),
        upstream_resource_id=row.upstream_resource_id,
        policy_note=getattr(row, "policy_note", None),
    )


def _safe_rows(source_domain: str | None = None, *, database_url: str | None = None) -> list[SourceWorkORM]:
    try:
        with get_session(database_url=database_url) as session:
            stmt = select(SourceWorkORM)
            if source_domain:
                stmt = stmt.where(SourceWorkORM.source_domain == source_domain)
            return list(session.execute(stmt).scalars().all())
    except RuntimeError:
        return []
    except SQLAlchemyError as exc:  # pragma: no cover
        raise SourceRegistryDatabaseError(str(exc)) from exc


def get_source_record_from_db(source_id: str, *, database_url: str | None = None) -> SourceRecord | None:
    rows = _safe_rows(database_url=database_url)
    for row in rows:
        if row.source_id == source_id:
            return _to_source_record(row)
    return None


def list_source_records_from_db(
    source_domain: str | None = None,
    *,
    database_url: str | None = None,
) -> list[SourceRecord]:
    return [_to_source_record(row) for row in _safe_rows(source_domain=source_domain, database_url=database_url)]


def merge_source_records(*record_groups: Iterable[SourceRecord]) -> list[SourceRecord]:
    merged: dict[str, SourceRecord] = {}
    for group in record_groups:
        for record in group:
            merged[record.source_id] = record
    return list(merged.values())
