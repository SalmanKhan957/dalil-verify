from __future__ import annotations

from typing import Protocol

from domains.hadith.contracts import HadithGradingContract


class HadithGradingRepository(Protocol):
    def get_grading_for_entry(self, canonical_entry_id: str) -> HadithGradingContract | None: ...
