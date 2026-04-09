from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class QueryFamilyDefinition:
    family_id: str
    domain: str
    route_type: str | None
    query_profile: str
    public_supported: bool
    needs_clarification: bool = False
    cue_phrases: tuple[str, ...] = ()
    example_queries: tuple[str, ...] = ()
    domain_cues: tuple[str, ...] = ()
    priority: int = 0


@dataclass(frozen=True, slots=True)
class ConceptDefinition:
    concept_id: str
    slug: str
    domain: str
    family: str
    label_en: str
    surface_forms: tuple[str, ...] = ()
    artifact_surface_forms: tuple[str, ...] = ()
    directive_biases: tuple[str, ...] = ()
    guidance_roles: tuple[str, ...] = ()
    canonical_ref: str | None = None


@dataclass(slots=True)
class QueryFamilyMatch:
    family_id: str
    domain: str
    route_type: str | None
    query_profile: str
    confidence: float
    public_supported: bool
    needs_clarification: bool
    matched_cues: tuple[str, ...] = ()
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConceptMatch:
    concept_id: str
    slug: str
    domain: str
    family: str
    confidence: float
    matched_terms: tuple[str, ...] = ()
    directive_biases: tuple[str, ...] = ()
    guidance_roles: tuple[str, ...] = ()
    canonical_ref: str | None = None
    debug: dict[str, Any] = field(default_factory=dict)
