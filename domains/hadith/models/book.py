from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HadithBook:
    collection_source_id: str
    book_number: int
    canonical_book_id: str
    title_en: str
    title_ar: str | None = None
    aliases: list[str] = field(default_factory=list)
