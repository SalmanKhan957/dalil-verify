from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VerifyQuranRequest(BaseModel):
    text: str = Field(..., min_length=1, description="User input to verify against Quran sources.")


class VerifyQuranResponse(BaseModel):
    query: str
    preferred_lane: str
    match_status: str
    confidence: str
    boundary_note: str
    best_match: dict[str, Any] | None
    exact_matches: list[dict[str, Any]] = Field(default_factory=list)
    strong_matches: list[dict[str, Any]] = Field(default_factory=list)
    also_related: list[dict[str, Any]]
    debug: dict[str, Any] | None = None