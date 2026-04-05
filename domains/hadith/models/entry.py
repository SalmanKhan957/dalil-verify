from __future__ import annotations

from dataclasses import dataclass, field

from domains.hadith.models.grading import HadithGrading


@dataclass(slots=True)
class HadithEntry:
    collection_source_id: str
    canonical_entry_id: str
    hadith_number: str
    canonical_ref: str
    book_number: int | None = None
    chapter_number: int | None = None
    english_text: str | None = None
    arabic_text: str | None = None
    narrator_chain_text: str | None = None
    matn_text: str | None = None
    grading: HadithGrading | None = None
    metadata_json: dict[str, object] = field(default_factory=dict)
