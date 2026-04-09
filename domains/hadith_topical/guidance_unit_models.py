from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class GuidanceUnitDocument:
    guidance_unit_id: str
    parent_hadith_ref: str
    collection_source_id: str
    span_text: str
    summary_text: str | None = None
    guidance_role: str = 'narrative_context'
    topic_family: str | None = None
    central_concept_ids: tuple[str, ...] = ()
    secondary_concept_ids: tuple[str, ...] = ()
    directness_score: float = 0.0
    answerability_score: float = 0.0
    narrative_penalty: float = 0.0
    span_start: int | None = None
    span_end: int | None = None
    numbering_quality: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
