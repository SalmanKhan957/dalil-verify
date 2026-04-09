from __future__ import annotations

import json
from pathlib import Path

from pipelines.indexing.hadith.build_hadith_topical_documents import build_documents


def enrich_records_file(input_path: str | Path, output_path: str | Path) -> None:
    records = json.loads(Path(input_path).read_text(encoding='utf-8'))
    documents = build_documents(records)
    Path(output_path).write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding='utf-8')
