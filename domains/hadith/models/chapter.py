from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HadithChapter:
    canonical_book_id: str
    chapter_number: int
    canonical_chapter_id: str
    title_en: str | None = None
    title_ar: str | None = None
