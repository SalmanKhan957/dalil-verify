from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

AYAH_LINE_RE = re.compile(r'^(\d+)\|(\d+)\|(.*)$')
EXPECTED_AYAH_COUNT = 6236


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Import a local single-file Quran translation into the CSV format expected '
            'by Dalil Verify translation display support.'
        )
    )
    parser.add_argument('--input-file', required=True, help='Path to the local translation text file.')
    parser.add_argument('--translation-name', required=True, help='Human-readable translation name.')
    parser.add_argument('--translator', default='', help='Translator name.')
    parser.add_argument('--language', default='en', help='Language code. Default: en')
    parser.add_argument('--source-id', default='local', help='Source identifier for provenance tracking.')
    parser.add_argument('--source-name', default='local_file', help='Source name for provenance tracking.')
    parser.add_argument(
        '--output-file',
        default='data/processed/quran_translations/quran_en_single_translation.csv',
        help='Output CSV path. Default: data/processed/quran_translations/quran_en_single_translation.csv',
    )
    parser.add_argument('--overwrite', action='store_true', help='Overwrite output file if it exists.')
    return parser.parse_args()


def iter_translation_rows(input_path: Path):
    with input_path.open('r', encoding='utf-8-sig') as f:
        for line_number, raw in enumerate(f, start=1):
            line = raw.rstrip('\n').strip()
            if not line or line.startswith('#'):
                continue
            match = AYAH_LINE_RE.match(line)
            if not match:
                raise ValueError(f'Unrecognized translation line format at line {line_number}: {line[:120]}')
            surah_no, ayah_no, text = match.groups()
            yield int(surah_no), int(ayah_no), text.strip()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input_file)
    output_path = Path(args.output_file)

    if not input_path.exists():
        raise SystemExit(f'Input file not found: {input_path}')

    if output_path.exists() and not args.overwrite:
        raise SystemExit(f'Output file already exists: {output_path}. Use --overwrite to replace it.')

    rows = list(iter_translation_rows(input_path))
    if len(rows) != EXPECTED_AYAH_COUNT:
        raise SystemExit(
            f'Expected {EXPECTED_AYAH_COUNT} ayah rows, found {len(rows)} in {input_path}. '
            'Check file format before importing.'
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                'surah_no',
                'ayah_no',
                'translation_name',
                'translator',
                'language',
                'source_id',
                'source_name',
                'text_display',
                'text_raw_html',
            ],
        )
        writer.writeheader()
        for surah_no, ayah_no, text in rows:
            writer.writerow(
                {
                    'surah_no': surah_no,
                    'ayah_no': ayah_no,
                    'translation_name': args.translation_name,
                    'translator': args.translator,
                    'language': args.language,
                    'source_id': args.source_id,
                    'source_name': args.source_name,
                    'text_display': text,
                    'text_raw_html': text,
                }
            )

    print(f'Imported {len(rows)} ayat into {output_path}')
    print(f'Translation name: {args.translation_name}')
    if args.translator:
        print(f'Translator: {args.translator}')


if __name__ == '__main__':
    main()
