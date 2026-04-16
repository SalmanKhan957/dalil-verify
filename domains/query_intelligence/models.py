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
    anti_cues: tuple[str, ...] = ()
    minimum_domain_cue_overlap: int = 0
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


@dataclass(slots=True)
class QueryNormalizationResult:
    raw_query: str
    normalized_query: str
    backend: str
    changed: bool
    confidence: float
    normalization_type: str
    did_change_meaning: bool
    safe_for_routing: bool
    notes: str = ''
    model: str | None = None
    used_hosted_model: bool = False
    attempted_hosted_model: bool = False
    hosted_model: str | None = None
    hosted_fallback_reason: str | None = None
    hosted_error_class: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'raw_query': self.raw_query,
            'normalized_query': self.normalized_query,
            'backend': self.backend,
            'changed': self.changed,
            'confidence': round(float(self.confidence or 0.0), 3),
            'normalization_type': self.normalization_type,
            'did_change_meaning': bool(self.did_change_meaning),
            'safe_for_routing': bool(self.safe_for_routing),
            'used_hosted_model': bool(self.used_hosted_model),
            'attempted_hosted_model': bool(self.attempted_hosted_model),
        }
        if self.notes:
            payload['notes'] = self.notes
        if self.model:
            payload['model'] = self.model
        if self.hosted_model:
            payload['hosted_model'] = self.hosted_model
        if self.hosted_fallback_reason:
            payload['hosted_fallback_reason'] = self.hosted_fallback_reason
        if self.hosted_error_class:
            payload['hosted_error_class'] = self.hosted_error_class
        return payload
