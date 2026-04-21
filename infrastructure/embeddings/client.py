"""OpenAI Embedding Client for DALIL Runtime Retrieval."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from infrastructure.config.settings import settings

_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIM = 1536

def embed_text(text: str) -> list[float] | None:
    """Fetch 1536-dim vector for a single query string from OpenAI."""
    if not settings.openai_api_key.strip():
        return None

    # Payload matching the backfill script logic
    payload = {
        "model": _EMBEDDING_MODEL,
        "input": text.replace("\n", " "),
        "dimensions": _EMBEDDING_DIM
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.openai_api_key}"
        },
        method="POST"
    )

    try:
        # Use the query normalization timeout as a safe baseline
        timeout = getattr(settings, 'query_normalization_timeout_seconds', 10.0)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_payload = json.loads(response.read().decode("utf-8"))
            # Standard OpenAI response format: data[0].embedding
            data = res_payload.get("data", [])
            if data and isinstance(data, list):
                return data[0].get("embedding")
    except Exception:
        # Silent failure allows candidate_generation.py to fall back to BM25
        return None
    return None