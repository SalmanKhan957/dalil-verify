from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HadithCollection:
    source_id: str
    work_slug: str
    display_name: str
    citation_label: str
    language_code: str
    upstream_provider: str | None = None
    upstream_collection_id: str | None = None
