from __future__ import annotations

from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from infrastructure.db.base import Base, TimestampMixin

json_type = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class HadithIngestionRunORM(TimestampMixin, Base):
    __tablename__ = "hadith_ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'completed_with_warnings', 'failed')",
            name="hadith_ingestion_runs_status_check",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_id: Mapped[int] = mapped_column(Integer, ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False)
    source_root: Mapped[str] = mapped_column(Text, nullable=False)
    upstream_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running", server_default="running")
    collections_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    books_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    chapters_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    entries_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    gradings_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    notes_json: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict, server_default="{}")
