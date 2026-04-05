from __future__ import annotations

from domains.hadith.citations.parser import parse_hadith_citation
from domains.hadith.citations.renderer import render_hadith_citation
from domains.hadith.retrieval.citation_lookup import HadithCitationLookupService


class HadithService:
    """Design-phase façade for the future Hadith domain."""

    def __init__(self, *, citation_lookup_service: HadithCitationLookupService | None = None) -> None:
        self.citation_lookup_service = citation_lookup_service or HadithCitationLookupService()

    def parse_citation(self, query: str):
        return parse_hadith_citation(query)

    def render_citation(self, citation) -> str:
        return render_hadith_citation(citation)

    def lookup_by_citation(self, query: str):
        citation = parse_hadith_citation(query)
        if citation is None:
            return None
        return self.citation_lookup_service.lookup(citation)
