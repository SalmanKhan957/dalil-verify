from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domains.hadith.contracts import HadithCitationReference
from domains.hadith.citations.renderer import render_hadith_citation
from domains.hadith.types import HadithEntryRecord
from domains.tafsir.types import TafsirOverlapHit


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
    hit: TafsirOverlapHit


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
    raw: dict[str, Any]


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


def build_tafsir_evidence(hits: list[TafsirOverlapHit] | None) -> list[TafsirEvidence]:
    return [TafsirEvidence(hit=hit) for hit in (hits or [])]


def build_hadith_evidence(entry: HadithEntryRecord | None, *, citation: HadithCitationReference | None = None) -> HadithEvidence | None:
    if entry is None:
        return None
    citation_string = render_hadith_citation(citation) if citation is not None else entry.canonical_ref_collection
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
        },
    )
