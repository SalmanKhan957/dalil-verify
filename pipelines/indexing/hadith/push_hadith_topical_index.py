from __future__ import annotations

import json
from pathlib import Path

from infrastructure.search.index_names import HADITH_TOPICAL_INDEX
from infrastructure.search.opensearch.hadith_topical_index import load_hadith_topical_mapping
from infrastructure.search.opensearch_client import OpenSearchClient


def push_documents_to_index(documents_path: str | Path) -> dict:
    client = OpenSearchClient.from_environment()
    if not client.is_enabled:
        raise RuntimeError('OpenSearch is not configured. Set OPENSEARCH_URL before pushing Hadith topical documents.')
    documents = json.loads(Path(documents_path).read_text(encoding='utf-8'))
    if not client.index_exists(index=HADITH_TOPICAL_INDEX):
        client.create_index(index=HADITH_TOPICAL_INDEX, body=load_hadith_topical_mapping())
    return client.bulk_index(index=HADITH_TOPICAL_INDEX, documents=documents)
