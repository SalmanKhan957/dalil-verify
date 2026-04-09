from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class HadithTopicalQuery:
    raw_query: str
    normalized_query: str
    topic_candidates: tuple[str, ...]
    query_profile: str = 'general_topic'
    language_hint: str | None = None
    topic_family: str | None = None
    directive_biases: tuple[str, ...] = ()
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HadithTopicalDocument:
    canonical_ref: str
    collection_source_id: str
    collection_slug: str
    collection_hadith_number: int | None
    book_number: int | None
    chapter_number: int | None
    numbering_quality: str | None
    english_text: str
    arabic_text: str | None = None
    english_narrator: str | None = None
    book_title_en: str | None = None
    chapter_title_en: str | None = None
    normalized_english_text: str = ''
    contextual_summary: str = ''
    topic_tags: tuple[str, ...] = ()
    subtopic_tags: tuple[str, ...] = ()
    directive_labels: tuple[str, ...] = ()
    topic_family: str | None = None
    guidance_role: str = 'narrative_incident'
    central_topic_score: float = 0.0
    answerability_score: float = 0.0
    narrative_specificity_score: float = 0.0
    incidental_topic_flags: tuple[str, ...] = ()
    normalized_topic_terms: tuple[str, ...] = ()
    normalized_alias_terms: tuple[str, ...] = ()
    moral_concepts: tuple[str, ...] = ()


@dataclass(slots=True)
class HadithTopicalCandidate:
    canonical_ref: str
    source_id: str
    retrieval_origin: str
    lexical_score: float | None = None
    vector_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None
    central_topic_score: float | None = None
    answerability_score: float | None = None
    narrative_specificity_score: float | None = None
    incidental_topic_penalty: float | None = None
    guidance_role: str | None = None
    topic_family: str | None = None
    matched_topics: tuple[str, ...] = ()
    matched_terms: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HadithTopicalCandidateGenerationRequest:
    query: HadithTopicalQuery
    collection_source_id: str | None = None
    candidate_limit: int = 12
    lexical_limit: int = 12
    allow_opensearch: bool = True


@dataclass(slots=True)
class HadithTopicalCandidateGenerationResult:
    candidates: tuple[HadithTopicalCandidate, ...]
    warnings: tuple[str, ...] = ()
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HadithTopicalResult:
    selected: tuple[HadithTopicalCandidate, ...]
    abstain: bool
    abstain_reason: str | None = None
    warnings: tuple[str, ...] = ()
    debug: dict[str, Any] = field(default_factory=dict)
