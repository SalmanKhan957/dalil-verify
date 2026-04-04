from __future__ import annotations

from services.tafsir.formatter import build_tafsir_citation, render_tafsir_label
from services.tafsir.types import TafsirOverlapHit


def _hit() -> TafsirOverlapHit:
    return TafsirOverlapHit(
        section_id=84552,
        canonical_section_id="tafsir:ibn-kathir-en:84552",
        work_id=1,
        source_id="tafsir:ibn-kathir-en",
        display_name="Tafsir Ibn Kathir (English)",
        citation_label="Tafsir Ibn Kathir",
        surah_no=112,
        ayah_start=1,
        ayah_end=4,
        anchor_verse_key="112:1",
        quran_span_ref="112:1-4",
        coverage_mode="inferred_from_empty_followers",
        coverage_confidence=0.95,
        text_plain="Say: He is Allah, the One.",
        text_html="<p>Say: He is Allah, the One.</p>",
        overlap_ayah_count=4,
        exact_span_match=True,
        contains_query_span=True,
        query_contains_section=True,
        span_width=4,
        anchor_distance=0,
    )


def test_render_tafsir_label_for_multi_ayah_span() -> None:
    assert render_tafsir_label(_hit()) == "Tafsir Ibn Kathir on Quran 112:1-4"


def test_build_tafsir_citation_returns_expected_fields() -> None:
    citation = build_tafsir_citation(_hit())

    assert citation.source_id == "tafsir:ibn-kathir-en"
    assert citation.canonical_section_id == "tafsir:ibn-kathir-en:84552"
    assert citation.citation_label == "Tafsir Ibn Kathir"
    assert citation.quran_span_ref == "112:1-4"
    assert citation.display_text == "Tafsir Ibn Kathir on Quran 112:1-4"
