from __future__ import annotations

from typing import Protocol

from services.tafsir.types import TafsirOverlapHit, TafsirOverlapQuery


class OverlapHitRepository(Protocol):
    def fetch_overlap_hits(self, query: TafsirOverlapQuery) -> list[TafsirOverlapHit]: ...


def validate_overlap_query(query: TafsirOverlapQuery) -> None:
    if query.ayah_start < 1:
        raise ValueError("ayah_start must be >= 1")
    if query.ayah_end < query.ayah_start:
        raise ValueError("ayah_end must be >= ayah_start")
    if query.limit < 1:
        raise ValueError("limit must be >= 1")
    if query.limit > 20:
        raise ValueError("limit must be <= 20 for Tafsir v1")


def sort_overlap_hits(hits: list[TafsirOverlapHit]) -> list[TafsirOverlapHit]:
    return sorted(
        hits,
        key=lambda hit: (
            not hit.exact_span_match,
            not hit.contains_query_span,
            -hit.overlap_ayah_count,
            hit.span_width,
            hit.anchor_distance,
            hit.section_id,
        ),
    )


class TafsirOverlapService:
    def __init__(self, repository: OverlapHitRepository) -> None:
        self.repository = repository

    def fetch(self, query: TafsirOverlapQuery) -> list[TafsirOverlapHit]:
        validate_overlap_query(query)
        return sort_overlap_hits(self.repository.fetch_overlap_hits(query))[: query.limit]
