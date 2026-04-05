from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.hadith.contracts import HadithEntryContract


@dataclass(slots=True)
class NormalizedHadithCollectionBatch:
    collection_source_id: str
    entries: list[HadithEntryContract]
    notes: list[str]


class HadithCollectionNormalizer:
    """Design-phase normalizer contract for incoming hadith collection payloads."""

    def normalize(self, payload: dict[str, Any]) -> NormalizedHadithCollectionBatch:
        raise NotImplementedError('hadith_normalization_not_implemented_yet')
