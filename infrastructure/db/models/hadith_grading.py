from __future__ import annotations

from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from infrastructure.db.base import Base, TimestampMixin

json_type = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class HadithGradingORM(TimestampMixin, Base):
    __tablename__ = "hadith_gradings"
    __table_args__ = (
        CheckConstraint("grade_label IN ('sahih', 'hasan', 'daif', 'unknown')", name="hadith_gradings_grade_label_check"),
        UniqueConstraint("entry_id", "grader_name", name="hadith_gradings_entry_grader_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(Integer, ForeignKey("hadith_entries.id", ondelete="CASCADE"), nullable=False)
    grade_label: Mapped[str] = mapped_column(String(32), nullable=False)
    grade_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grader_name: Mapped[str] = mapped_column(String(255), nullable=False, default="collection_default", server_default="collection_default")
    provenance_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict, server_default="{}")
