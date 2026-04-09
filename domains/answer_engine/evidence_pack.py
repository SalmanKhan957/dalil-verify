from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domains.hadith.contracts import HadithCitationReference
from domains.hadith.citations.renderer import render_hadith_citation
from domains.hadith.types import HadithEntryRecord


def _clean_hadith_book_title(value: Any, *, language: str) -> str | None:
    text = ' '.join(str(value or '').split()).strip()
    if not text:
        return None
    if language == 'en':
        lower = text.lower()
        if lower in {'chapter', 'chapter:'}:
            return None
        if lower.startswith('chapter:'):
            stripped = text.split(':', 1)[1].strip()
            return stripped or None
        return text
    if language == 'ar':
        if text in {'باب', 'باب:'}:
            return None
        if text.startswith('باب'):
            stripped = text[3:].strip(' :،-ـ')
            return stripped or None
        return text
    return text


@dataclass(slots=True)
class QuranEvidence:
    citation_string: str
    canonical_source_id: str
    quran_source_id: str | None
    surah_no: int
    ayah_start: int
    ayah_end: int
    surah_name_en: str | None
    surah_name_ar: str | None
    arabic_text: str | None
    translation_text: str | None
    translation_source_id: str | None
    raw: dict[str, Any]


@dataclass(slots=True)
class TafsirEvidence:
    hit: Any


@dataclass(slots=True)
class HadithEvidence:
    citation_string: str
    canonical_ref: str
    collection_source_id: str
    source_id: str
    collection_slug: str
    collection_hadith_number: int
    book_number: int
    chapter_number: int | None
    in_book_hadith_number: int | None
    english_narrator: str | None
    english_text: str | None
    arabic_text: str | None
    narrator_chain_text: str | None
    matn_text: str | None
    grading_label: str | None
    grading_text: str | None
    snippet: str | None = None
    retrieval_method: str | None = None
    matched_terms: tuple[str, ...] = ()
    guidance_unit_id: str | None = None
    guidance_summary: str | None = None
    source_excerpt: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvidencePack:
    query: str
    route_type: str
    action_type: str
    quran: QuranEvidence | None = None
    tafsir: list[TafsirEvidence] = field(default_factory=list)
    hadith: HadithEvidence | None = None
    resolution: dict[str, Any] | None = None
    verifier_result: dict[str, Any] | None = None
    quote_payload: str | None = None
    selected_domains: list[str] = field(default_factory=list)
    response_mode: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


def build_quran_evidence(quran_span: dict[str, Any] | None) -> QuranEvidence | None:
    if not quran_span:
        return None

    translation = quran_span.get("translation") or {}
    return QuranEvidence(
        citation_string=str(quran_span.get("citation_string") or ""),
        canonical_source_id=str(quran_span.get("canonical_source_id") or ""),
        quran_source_id=quran_span.get("source_id"),
        surah_no=int(quran_span.get("surah_no") or 0),
        ayah_start=int(quran_span.get("ayah_start") or 0),
        ayah_end=int(quran_span.get("ayah_end") or 0),
        surah_name_en=quran_span.get("surah_name_en"),
        surah_name_ar=quran_span.get("surah_name_ar"),
        arabic_text=quran_span.get("arabic_text"),
        translation_text=translation.get("text"),
        translation_source_id=translation.get("source_id"),
        raw=quran_span,
    )


def build_tafsir_evidence(hits: list[Any] | None) -> list[TafsirEvidence]:
    return [TafsirEvidence(hit=hit) for hit in (hits or [])]


def build_hadith_evidence(entry: HadithEntryRecord | None, *, citation: HadithCitationReference | None = None, snippet: str | None = None, retrieval_method: str | None = None, matched_terms: tuple[str, ...] = (), authority_source: str | None = None, retrieval_origin: str | None = None, matched_topics: tuple[str, ...] = (), central_topic_score: float | None = None, answerability_score: float | None = None, guidance_role: str | None = None, topic_family: str | None = None, fusion_score: float | None = None, rerank_score: float | None = None, lexical_score: float | None = None, vector_score: float | None = None, guidance_unit_id: str | None = None, guidance_summary: str | None = None, source_excerpt: str | None = None) -> HadithEvidence | None:
    if entry is None:
        return None
    citation_string = render_hadith_citation(citation) if citation is not None else entry.canonical_ref_collection
    metadata = dict(entry.metadata_json or {})
    return HadithEvidence(
        citation_string=citation_string,
        canonical_ref=entry.canonical_ref_collection,
        collection_source_id=entry.collection_source_id,
        source_id=entry.collection_source_id,
        collection_slug=(citation.collection_slug if citation is not None else entry.collection_source_id.replace('hadith:', '')),
        collection_hadith_number=entry.collection_hadith_number,
        book_number=entry.book_number,
        chapter_number=entry.chapter_number,
        in_book_hadith_number=entry.in_book_hadith_number,
        english_narrator=entry.english_narrator,
        english_text=entry.english_text,
        arabic_text=entry.arabic_text,
        narrator_chain_text=entry.narrator_chain_text,
        matn_text=entry.matn_text,
        grading_label=(entry.grading.grade_label.value if entry.grading else None),
        grading_text=(entry.grading.grade_text if entry.grading else None),
        snippet=snippet,
        retrieval_method=retrieval_method,
        matched_terms=matched_terms,
        guidance_unit_id=guidance_unit_id,
        guidance_summary=guidance_summary,
        source_excerpt=source_excerpt,
        raw={
            'canonical_ref_collection': entry.canonical_ref_collection,
            'canonical_ref_book_hadith': entry.canonical_ref_book_hadith,
            'canonical_ref_book_chapter_hadith': entry.canonical_ref_book_chapter_hadith,
            'collection_hadith_number': entry.collection_hadith_number,
            'book_number': entry.book_number,
            'chapter_number': entry.chapter_number,
            'in_book_hadith_number': entry.in_book_hadith_number,
            'english_narrator': entry.english_narrator,
            'english_text': entry.english_text,
            'arabic_text': entry.arabic_text,
            'grading_label': (entry.grading.grade_label.value if entry.grading else None),
            'grading_text': (entry.grading.grade_text if entry.grading else None),
            'snippet': snippet,
            'retrieval_method': retrieval_method,
            'matched_terms': list(matched_terms),
            'authority_source': authority_source,
            'retrieval_origin': retrieval_origin,
            'matched_topics': list(matched_topics),
            'central_topic_score': central_topic_score,
            'answerability_score': answerability_score,
            'guidance_role': guidance_role,
            'topic_family': topic_family,
            'fusion_score': fusion_score,
            'rerank_score': rerank_score,
            'lexical_score': lexical_score,
            'vector_score': vector_score,
            'guidance_unit_id': guidance_unit_id,
            'guidance_summary': guidance_summary,
            'source_excerpt': source_excerpt,
            'reference_url': metadata.get('reference_url'),
            'in_book_reference_text': metadata.get('in_book_reference_text'),
            'public_collection_number': metadata.get('public_collection_number'),
            'book_title_en': _clean_hadith_book_title(metadata.get('book_title_en'), language='en'),
            'book_title_ar': _clean_hadith_book_title(metadata.get('book_title_ar'), language='ar'),
            'numbering_quality': metadata.get('numbering_quality'),
        },
    )
