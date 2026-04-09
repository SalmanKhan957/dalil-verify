from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipelines.indexing.hadith.build_hadith_topical_documents import build_documents


def main() -> int:
    parser = argparse.ArgumentParser(description='Build enriched Hadith topical documents from canonical Hadith records JSON.')
    parser.add_argument('--input', required=True, help='Path to input JSON file containing a list of canonical Hadith records.')
    parser.add_argument('--output', required=True, help='Path to write enriched Hadith topical documents JSON.')
    args = parser.parse_args()

    records = json.loads(Path(args.input).read_text(encoding='utf-8'))
    documents = build_documents(records)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {len(documents)} topical documents -> {output_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
