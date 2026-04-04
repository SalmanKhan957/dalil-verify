from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SourceRecord(BaseModel):
    source_id: str = Field(..., description="Stable source/work identifier.")
    source_domain: Literal["quran", "tafsir", "hadith"] = Field(..., description="Top-level source domain.")
    source_kind: Literal["canonical_text", "translation", "commentary", "hadith_collection"] = Field(
        ...,
        description="Source/work kind used for rendering and policy decisions.",
    )
    display_name: str = Field(..., description="Human-readable source/work name.")
    citation_label: str = Field(..., description="Label to use when citing this source.")
    language: str = Field(..., description="Primary content language.")
    enabled: bool = Field(default=True, description="Whether the source is currently available for retrieval.")
    approved_for_answering: bool = Field(
        default=True,
        description="Whether the source is approved for answer composition in DALIL.",
    )
    default_for_explain: bool = Field(
        default=False,
        description="Whether this source should be selected by default for explain-mode requests in its domain.",
    )
    supports_quran_composition: bool = Field(
        default=False,
        description="Whether this source may be composed alongside Quran evidence in bounded answer flows.",
    )
    priority_rank: int = Field(
        default=1000,
        description="Lower numbers win when choosing between multiple approved sources in the same role.",
    )
    upstream_resource_id: int | None = Field(
        default=None,
        description="Optional upstream resource identifier used for provenance and governance.",
    )
    policy_note: str | None = Field(
        default=None,
        description="Optional note for trust boundaries or rendering constraints.",
    )
