from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExplainQuranReferenceRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Explicit Quran reference to explain.")


class ExplainQuranReferenceResponse(BaseModel):
    ok: bool
    intent: str
    query: str
    resolution: dict[str, Any]
    quran_span: dict[str, Any] | None = None
    error: str | None = None
