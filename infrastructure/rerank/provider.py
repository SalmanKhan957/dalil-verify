from __future__ import annotations

from typing import Protocol


class RerankProvider(Protocol):
    def rerank(self, query: str, documents: list[str]) -> list[float]: ...
