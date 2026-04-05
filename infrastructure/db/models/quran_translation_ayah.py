from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base, TimestampMixin


class QuranTranslationAyahORM(TimestampMixin, Base):
    __tablename__ = "quran_translation_ayahs"
    __table_args__ = (
        CheckConstraint("ayah_no >= 1", name="quran_translation_ayahs_ayah_no_check"),
        UniqueConstraint(
            "work_id",
            "surah_no",
            "ayah_no",
            name="quran_translation_ayahs_work_surah_ayah_unique",
        ),
        Index("idx_quran_translation_ayahs_work_surah", "work_id", "surah_no"),
        Index("idx_quran_translation_ayahs_work_surah_ayah", "work_id", "surah_no", "ayah_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False)
    surah_no: Mapped[int] = mapped_column(ForeignKey("quran_surahs.surah_no", ondelete="RESTRICT"), nullable=False)
    ayah_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text_display: Mapped[str] = mapped_column(Text, nullable=False)
    text_raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    translator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(16), nullable=False)
