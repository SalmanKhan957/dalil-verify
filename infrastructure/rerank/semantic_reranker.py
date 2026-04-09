from __future__ import annotations

from infrastructure.rerank.provider import RerankProvider


class NoOpSemanticReranker:
    """Phase-1 placeholder. Real reranking lands later."""

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        return [0.0 for _ in documents]
