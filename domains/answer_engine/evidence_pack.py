from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domains.tafsir.types import TafsirOverlapHit


@dataclass(slots=True)
class QuranEvidence:
    citation_string: str
    canonical_source_id: str
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
class EvidencePack:
    query: str
    route_type: str
    action_type: str
    quran: QuranEvidence | None = None
    tafsir: list[TafsirEvidence] = field(default_factory=list)
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
