from __future__ import annotations

from shared.schemas.source_citation import SourceCitation
from services.answer_engine.evidence_pack import EvidencePack, QuranEvidence, TafsirEvidence
from services.tafsir.formatter import render_tafsir_label


QURAN_ARABIC_SOURCE_ID = "quran:tanzil-simple"



def render_quran_citation(quran: QuranEvidence) -> SourceCitation:
    return SourceCitation(
        source_id=QURAN_ARABIC_SOURCE_ID,
        citation_text=quran.citation_string,
        canonical_ref=quran.canonical_source_id,
        source_domain="quran",
    )



def render_tafsir_citation(tafsir: TafsirEvidence) -> SourceCitation:
    hit = tafsir.hit
    return SourceCitation(
        source_id=hit.source_id,
        citation_text=render_tafsir_label(hit),
        canonical_ref=hit.canonical_section_id,
        source_domain="tafsir",
    )



def render_citation_list(evidence: EvidencePack) -> list[SourceCitation]:
    citations: list[SourceCitation] = []
    if evidence.quran is not None:
        citations.append(render_quran_citation(evidence.quran))
    citations.extend(render_tafsir_citation(item) for item in evidence.tafsir)
    return citations
