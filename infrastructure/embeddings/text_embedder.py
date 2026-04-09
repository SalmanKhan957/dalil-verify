from __future__ import annotations

from infrastructure.embeddings.provider import EmbeddingProvider


class NoOpTextEmbedder:
    """Phase-1 placeholder embedder. Returns an empty embedding."""

    def embed(self, text: str) -> list[float]:
        return []
