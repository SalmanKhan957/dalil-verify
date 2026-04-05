from __future__ import annotations

from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from infrastructure.db.base import Base, TimestampMixin

json_type = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class HadithEntryORM(TimestampMixin, Base):
    __tablename__ = "hadith_entries"
    __table_args__ = (
        CheckConstraint("collection_hadith_number >= 1", name="hadith_entries_collection_number_check"),
        CheckConstraint(
            "in_book_hadith_number IS NULL OR in_book_hadith_number >= 1",
            name="hadith_entries_in_book_number_check",
        ),
        UniqueConstraint("canonical_entry_id", name="hadith_entries_canonical_entry_id_unique"),
        UniqueConstraint("canonical_ref_collection", name="hadith_entries_canonical_ref_collection_unique"),
        UniqueConstraint("work_id", "collection_hadith_number", name="hadith_entries_work_collection_number_unique"),
        UniqueConstraint("work_id", "upstream_entry_id", name="hadith_entries_work_upstream_entry_id_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_id: Mapped[int] = mapped_column(Integer, ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False)
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("hadith_books.id", ondelete="RESTRICT"), nullable=False)
    chapter_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("hadith_chapters.id", ondelete="RESTRICT"), nullable=True)
    canonical_entry_id: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_ref_collection: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_ref_book_hadith: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_ref_book_chapter_hadith: Mapped[str | None] = mapped_column(String(255), nullable=True)
    collection_hadith_number: Mapped[int] = mapped_column(Integer, nullable=False)
    in_book_hadith_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upstream_entry_id: Mapped[int] = mapped_column(Integer, nullable=False)
    upstream_book_id: Mapped[int] = mapped_column(Integer, nullable=False)
    upstream_chapter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    english_narrator: Mapped[str | None] = mapped_column(Text, nullable=True)
    english_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    arabic_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrator_chain_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    matn_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict, server_default="{}")
    raw_json: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict, server_default="{}")
