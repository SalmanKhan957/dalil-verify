from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HadithGrading:
    grade_label: str
    grade_text: str | None = None
    grader_name: str | None = None
    provenance_note: str | None = None
    metadata_json: dict[str, object] = field(default_factory=dict)
