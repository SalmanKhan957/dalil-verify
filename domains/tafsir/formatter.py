from __future__ import annotations

from domains.tafsir.types import TafsirCitationBlock, TafsirOverlapHit


def render_tafsir_label(hit: TafsirOverlapHit) -> str:
    return f"{hit.citation_label} on Quran {hit.quran_span_ref}"


def build_tafsir_citation(hit: TafsirOverlapHit) -> TafsirCitationBlock:
    return TafsirCitationBlock(
        source_id=hit.source_id,
        canonical_section_id=hit.canonical_section_id,
        citation_label=hit.citation_label,
        quran_span_ref=hit.quran_span_ref,
        display_text=render_tafsir_label(hit),
    )
