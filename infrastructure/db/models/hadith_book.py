from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from infrastructure.db.base import Base, TimestampMixin

json_type = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class HadithBookORM(TimestampMixin, Base):
    __tablename__ = "hadith_books"
    __table_args__ = (
        UniqueConstraint("canonical_book_id", name="hadith_books_canonical_book_id_unique"),
        UniqueConstraint("work_id", "book_number", name="hadith_books_work_book_number_unique"),
        UniqueConstraint("work_id", "upstream_book_id", name="hadith_books_work_upstream_book_id_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_id: Mapped[int] = mapped_column(Integer, ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False)
    canonical_book_id: Mapped[str] = mapped_column(String(255), nullable=False)
    book_number: Mapped[int] = mapped_column(Integer, nullable=False)
    upstream_book_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title_en: Mapped[str] = mapped_column(String(255), nullable=False)
    title_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict, server_default="{}")
