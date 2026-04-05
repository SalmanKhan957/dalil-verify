from __future__ import annotations

from typing import Protocol

from domains.hadith.contracts import HadithCollectionContract


class HadithCollectionRepository(Protocol):
    def get_collection_by_source_id(self, source_id: str) -> HadithCollectionContract | None: ...
