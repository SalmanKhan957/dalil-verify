from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base, TimestampMixin


class QuranSurahORM(TimestampMixin, Base):
    __tablename__ = "quran_surahs"

    surah_no: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    surah_name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    surah_name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    ayah_count: Mapped[int] = mapped_column(Integer, nullable=False)
