from __future__ import annotations

import json
from pathlib import Path

from infrastructure.embeddings.text_embedder import NoOpTextEmbedder


def embed_documents(documents_path: str | Path, output_path: str | Path) -> None:
    embedder = NoOpTextEmbedder()
    documents = json.loads(Path(documents_path).read_text(encoding='utf-8'))
    for document in documents:
        document['embedding_main'] = embedder.embed(document.get('english_text', ''))
        document['embedding_contextual'] = embedder.embed(document.get('contextual_summary', ''))
    Path(output_path).write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding='utf-8')
