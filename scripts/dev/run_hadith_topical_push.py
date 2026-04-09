from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipelines.indexing.hadith.push_hadith_topical_index import push_documents_to_index


def main() -> int:
    parser = argparse.ArgumentParser(description='Push enriched Hadith topical documents into OpenSearch.')
    parser.add_argument('--documents', required=True, help='Path to JSON file containing enriched Hadith topical documents.')
    args = parser.parse_args()

    result = push_documents_to_index(Path(args.documents))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
