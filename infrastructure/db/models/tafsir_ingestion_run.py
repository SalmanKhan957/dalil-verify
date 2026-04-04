from __future__ import annotations

from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from infrastructure.db.base import Base, TimestampMixin

json_type = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class TafsirIngestionRunORM(TimestampMixin, Base):
    __tablename__ = "tafsir_ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'completed_with_warnings', 'failed')",
            name="tafsir_ingestion_runs_status_check",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False)
    resource_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_root: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    chapters_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    raw_rows_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sections_built: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    notes_json: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict, server_default="{}")
