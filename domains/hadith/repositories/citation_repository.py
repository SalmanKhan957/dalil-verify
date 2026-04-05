from __future__ import annotations

from typing import Protocol

from domains.hadith.contracts import HadithCitationReference, HadithEntryContract


class HadithCitationRepository(Protocol):
    def get_by_citation(self, citation: HadithCitationReference) -> HadithEntryContract | None: ...
