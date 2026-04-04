from __future__ import annotations

from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    source_id: str = Field(..., description="Stable source/work identifier from the source registry.")
    citation_text: str = Field(..., description="Rendered citation text shown to the user.")
    canonical_ref: str | None = Field(default=None, description="Canonical verse/hadith/span reference when relevant.")
    source_domain: str = Field(..., description="Top-level source domain.")
