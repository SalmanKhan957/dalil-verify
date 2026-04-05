from __future__ import annotations

import pytest

from domains.tafsir.overlap import TafsirOverlapService, validate_overlap_query
from domains.tafsir.types import TafsirOverlapHit, TafsirOverlapQuery


class _FakeRepository:
    def __init__(self, hits):
        self._hits = hits

    def fetch_overlap_hits(self, query: TafsirOverlapQuery):
        return list(self._hits)


def _hit(*, section_id: int, exact: bool, contains: bool, overlap: int, width: int, distance: int) -> TafsirOverlapHit:
    return TafsirOverlapHit(
        section_id=section_id,
        canonical_section_id=f"tafsir:ibn-kathir-en:{section_id}",
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
        text_plain="text",
        text_html="<p>text</p>",
        overlap_ayah_count=overlap,
        exact_span_match=exact,
        contains_query_span=contains,
        query_contains_section=False,
        span_width=width,
        anchor_distance=distance,
    )


def test_overlap_service_sorts_hits_by_policy() -> None:
    hits = [
        _hit(section_id=3, exact=False, contains=True, overlap=2, width=6, distance=3),
        _hit(section_id=1, exact=True, contains=True, overlap=4, width=4, distance=0),
        _hit(section_id=2, exact=False, contains=True, overlap=4, width=8, distance=1),
    ]
    service = TafsirOverlapService(_FakeRepository(hits))

    ordered = service.fetch(TafsirOverlapQuery(work_id=1, surah_no=112, ayah_start=1, ayah_end=4, limit=5))

    assert [hit.section_id for hit in ordered] == [1, 2, 3]


def test_overlap_query_validation_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError, match="limit"):
        validate_overlap_query(TafsirOverlapQuery(work_id=1, surah_no=1, ayah_start=1, ayah_end=1, limit=0))
