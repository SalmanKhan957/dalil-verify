from __future__ import annotations

from domains.hadith.ingestion.normalizer import HadithCollectionNormalizer


class HadithCollectionIngestionService:
    def __init__(self, normalizer: HadithCollectionNormalizer | None = None) -> None:
        self.normalizer = normalizer or HadithCollectionNormalizer()

    def ingest(self, payload: dict[str, object]) -> None:
        raise NotImplementedError('hadith_ingestion_not_implemented_yet')
