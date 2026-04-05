from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from infrastructure.db.base import Base, TimestampMixin

json_type = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class HadithChapterORM(TimestampMixin, Base):
    __tablename__ = "hadith_chapters"
    __table_args__ = (
        UniqueConstraint("canonical_chapter_id", name="hadith_chapters_canonical_chapter_id_unique"),
        UniqueConstraint("work_id", "book_id", "chapter_number", name="hadith_chapters_work_book_chapter_number_unique"),
        UniqueConstraint("work_id", "upstream_chapter_id", name="hadith_chapters_work_upstream_chapter_id_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_id: Mapped[int] = mapped_column(Integer, ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False)
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("hadith_books.id", ondelete="RESTRICT"), nullable=False)
    canonical_chapter_id: Mapped[str] = mapped_column(String(255), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    upstream_chapter_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict, server_default="{}")
