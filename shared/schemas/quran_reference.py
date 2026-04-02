# shared/schemas/quran_reference.py

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class QuranReferenceResolution:
    resolved: bool
    source_type: str
    resolution_type: str
    canonical_source_id: str | None
    surah_no: int | None
    ayah_start: int | None
    ayah_end: int | None
    confidence: float
    normalized_query: str
    parse_type: str | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)