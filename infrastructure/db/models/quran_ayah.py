from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base, TimestampMixin


class QuranAyahORM(TimestampMixin, Base):
    __tablename__ = "quran_ayahs"
    __table_args__ = (
        CheckConstraint("ayah_no >= 1", name="quran_ayahs_ayah_no_check"),
        UniqueConstraint("work_id", "surah_no", "ayah_no", name="quran_ayahs_work_surah_ayah_unique"),
        UniqueConstraint("canonical_source_id", name="quran_ayahs_canonical_source_id_unique"),
        Index("idx_quran_ayahs_work_surah", "work_id", "surah_no"),
        Index("idx_quran_ayahs_work_surah_ayah", "work_id", "surah_no", "ayah_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False)
    surah_no: Mapped[int] = mapped_column(ForeignKey("quran_surahs.surah_no", ondelete="RESTRICT"), nullable=False)
    ayah_no: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    citation_string: Mapped[str] = mapped_column(String(64), nullable=False)
    text_display: Mapped[str] = mapped_column(Text, nullable=False)
    text_normalized_light: Mapped[str] = mapped_column(Text, nullable=False)
    text_normalized_aggressive: Mapped[str] = mapped_column(Text, nullable=False)
    bismillah: Mapped[str | None] = mapped_column(Text, nullable=True)
