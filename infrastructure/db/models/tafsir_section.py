from __future__ import annotations

from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from infrastructure.db.base import Base, TimestampMixin

json_type = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class TafsirSectionORM(TimestampMixin, Base):
    __tablename__ = "tafsir_sections"
    __table_args__ = (
        CheckConstraint("ayah_start >= 1 AND ayah_end >= ayah_start", name="tafsir_sections_ayah_bounds_check"),
        CheckConstraint(
            "coverage_mode IN ('explicit_range', 'inferred_from_empty_followers', 'anchor_only')",
            name="tafsir_sections_coverage_mode_check",
        ),
        UniqueConstraint("work_id", "upstream_entry_id", name="tafsir_sections_work_upstream_entry_unique"),
        Index("idx_tafsir_sections_work_surah", "work_id", "surah_no"),
        Index("idx_tafsir_sections_work_surah_start_end", "work_id", "surah_no", "ayah_start", "ayah_end"),
        Index("idx_tafsir_sections_anchor", "work_id", "anchor_verse_key"),
        Index("idx_tafsir_sections_span_ref", "work_id", "quran_span_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False)

    canonical_section_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    upstream_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    upstream_resource_id: Mapped[int] = mapped_column(Integer, nullable=False)
    upstream_entry_id: Mapped[int] = mapped_column(nullable=False)

    language_code: Mapped[str] = mapped_column(String(16), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    surah_no: Mapped[int] = mapped_column(Integer, nullable=False)
    ayah_start: Mapped[int] = mapped_column(Integer, nullable=False)
    ayah_end: Mapped[int] = mapped_column(Integer, nullable=False)
    anchor_verse_key: Mapped[str] = mapped_column(String(32), nullable=False)
    quran_span_ref: Mapped[str] = mapped_column(String(32), nullable=False)

    coverage_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    coverage_confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)

    text_html: Mapped[str] = mapped_column(Text, nullable=False)
    text_plain: Mapped[str] = mapped_column(Text, nullable=False)
    text_plain_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    source_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_manifest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_json: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False)
