from __future__ import annotations

from domains.hadith.contracts import HadithCitationLookupResult, HadithCitationReference


class HadithCitationLookupService:
    """Design-phase service contract for deterministic Hadith citation lookup."""

    def __init__(self, repository: object | None = None) -> None:
        self.repository = repository

    def lookup(self, citation: HadithCitationReference) -> HadithCitationLookupResult:
        return HadithCitationLookupResult(resolved=False, citation=citation, entry=None, warnings=['hadith_lookup_not_implemented_yet'], error='hadith_not_supported_yet')
