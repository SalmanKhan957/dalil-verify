from __future__ import annotations

import argparse
import json
from pathlib import Path

from infrastructure.search.index_names import HADITH_GUIDANCE_UNIT_INDEX
from infrastructure.search.opensearch_client import OpenSearchClient

REPO_ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = REPO_ROOT / 'infrastructure' / 'search' / 'opensearch' / 'hadith_guidance_unit_mapping.json'


def load_documents(path: Path) -> list[dict]:
    documents: list[dict] = []
    with path.open('r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                documents.append(json.loads(line))
    return documents


def main() -> None:
    parser = argparse.ArgumentParser(description='Index Hadith guidance-unit artifact into OpenSearch.')
    parser.add_argument('--artifact', default='data/processed/hadith_topical/guidance_units.v1.jsonl')
    parser.add_argument('--index', default=HADITH_GUIDANCE_UNIT_INDEX)
    parser.add_argument('--batch-size', type=int, default=500)
    args = parser.parse_args()

    artifact = Path(args.artifact)
    client = OpenSearchClient.from_environment()
    if not client.is_enabled:
        raise RuntimeError('OpenSearch is not configured; set OPENSEARCH_URL and related credentials.')
    mapping = json.loads(MAPPING_PATH.read_text(encoding='utf-8'))
    if not client.index_exists(index=args.index):
        client.create_index(index=args.index, body=mapping)
    documents = load_documents(artifact)
    for start in range(0, len(documents), max(1, int(args.batch_size))):
        batch = documents[start:start + max(1, int(args.batch_size))]
        client.bulk_index(index=args.index, documents=batch, id_field='guidance_unit_id')
    print(json.dumps({'indexed_count': len(documents), 'index': args.index, 'artifact': str(artifact)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':  # pragma: no cover
    main()
