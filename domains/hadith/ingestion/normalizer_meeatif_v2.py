"""Normalizer for bukhari_enriched_v2.json — the pre-enriched Sahih al-Bukhari corpus.

This normalizer consumes the enriched-v2 schema produced by the offline enrichment
pipeline and maps it to DALIL canonical ingestion contracts. It also joins against
the original ``Sahih al-Bukhari.json`` to recover the ``Arabic_Text`` field which
was not carried forward during enrichment.

Field mapping (enriched_v2 → canonical):
  hadith_global_num       → collection_hadith_number (int, direct)
  hadith_id "bukhari:N"   → strip prefix, build "hadith:sahih-al-bukhari-en:N"
  kitab_num               → book_number (int, direct)
  kitab_title_english/ar  → hadith_books title_en / title_ar
  in_book_reference       → parsed via regex for in_book_hadith_number
  narrator                → english_narrator, narrator_chain_text
  matn_text               → matn_text (pre-split, no regex)
  full_text               → english_text
  Arabic_Text (from join) → arabic_text
  grade                   → hadith_gradings
  is_stub = true          → skipped entirely
  enrichment fields       → metadata_json
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from domains.hadith.types import (
    HadithCollectionBatch,
    HadithCollectionSeed,
    HadithGradeLabel,
    HadithIngestionManifest,
    NormalizedHadithBook,
    NormalizedHadithEntry,
    NormalizedHadithGrading,
)

_HADITH_NUM_RE = re.compile(r"(?:bukhari:)(\d+)")
_IN_BOOK_REF_RE = re.compile(r"(?i)book\s+(\d+)\s*,\s*hadith\s+(\d+)")
_REFERENCE_URL_NUM_RE = re.compile(r"(?i)(?:^|/)bukhari:(\d+)(?:$|[/?#])")


@dataclass(slots=True)
class MeeAtifEnrichedV2NormalizerConfig:
    collection_slug: str = 'sahih-al-bukhari-en'
    collection_source_id: str = 'hadith:sahih-al-bukhari-en'
    display_name: str = 'Sahih al-Bukhari (English)'
    citation_label: str = 'Sahih al-Bukhari'
    author_name: str | None = 'Imam al-Bukhari'
    language_code: str = 'en'
    upstream_provider: str = 'meeatif_hadith_datasets'
    enabled: bool = True
    approved_for_answering: bool = False
    priority_rank: int = 1000
    version_label: str | None = 'meeatif-bukhari-enriched-v2'
    policy_note: str | None = (
        'MeeAtif/hadith_datasets enriched-v2 corpus with semantic domain tags, '
        'synthetic baab labels, query family routing, and direct prophetic statement flags. '
        'Arabic text sourced from original dataset via join on hadith_global_num.'
    )
    arabic_source_file: str | None = None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_hadith_number_from_id(hadith_id: str | None) -> int | None:
    """Extract integer N from 'bukhari:N'."""
    if not hadith_id:
        return None
    match = _HADITH_NUM_RE.search(str(hadith_id).strip())
    if not match:
        return None
    return int(match.group(1))


def _parse_in_book_reference(text: str | None) -> tuple[int, int] | None:
    """Parse 'Book X, Hadith Y' → (book_number, in_book_hadith_number)."""
    if not text:
        return None
    match = _IN_BOOK_REF_RE.search(text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _parse_collection_hadith_number_from_url(url: str | None) -> int | None:
    """Parse hadith number from sunnah.com reference URL (old JSON)."""
    if not url:
        return None
    match = _REFERENCE_URL_NUM_RE.search(url.strip())
    if not match:
        return None
    return int(match.group(1))


def _normalize_grade(grade_text: str | None) -> NormalizedHadithGrading | None:
    text = _clean(grade_text)
    if not text:
        return None
    normalized = text.casefold()
    if 'sahih' in normalized:
        label = HadithGradeLabel.SAHIH
    elif 'hasan' in normalized:
        label = HadithGradeLabel.HASAN
    elif any(token in normalized for token in ('daif', 'daeef', 'weak')):
        label = HadithGradeLabel.DAIF
    else:
        label = HadithGradeLabel.UNKNOWN
    return NormalizedHadithGrading(
        grade_label=label,
        grade_text=text,
        grader_name='meeatif_dataset',
        provenance_note='Imported from MeeAtif/hadith_datasets enriched-v2 grade field.',
        metadata_json={'source_dataset': 'meeatif/hadith_datasets', 'enrichment_version': 'v2'},
    )


def _build_arabic_lookup(arabic_source_file: str | Path | None) -> dict[int, str]:
    """Build a lookup {hadith_number: Arabic_Text} from the original JSON."""
    if arabic_source_file is None:
        return {}
    path = Path(arabic_source_file)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, list):
        return {}
    lookup: dict[int, str] = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        arabic = _clean(row.get('Arabic_Text'))
        if not arabic:
            continue
        ref_url = _clean(row.get('Reference'))
        num = _parse_collection_hadith_number_from_url(ref_url)
        if num is not None:
            lookup[num] = arabic
    return lookup


class MeeAtifEnrichedV2Normalizer:
    """Normalize the enriched-v2 Bukhari dataset into DALIL canonical contracts.

    Arabic text is sourced from the original ``Sahih al-Bukhari.json`` via a
    join on ``hadith_global_num`` because the enrichment script did not carry
    forward the ``Arabic_Text`` field.
    """

    def __init__(self, *, config: MeeAtifEnrichedV2NormalizerConfig | None = None) -> None:
        self.config = config or MeeAtifEnrichedV2NormalizerConfig()

    def normalize(self, payload: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> HadithCollectionBatch:
        if not isinstance(payload, list):
            raise TypeError('enriched_v2_payload_must_be_list')
        if not payload:
            raise ValueError('enriched_v2_payload_empty')

        arabic_lookup = _build_arabic_lookup(self.config.arabic_source_file)
        collection_name = _clean(payload[0].get('source')) or self.config.display_name

        collection_seed = HadithCollectionSeed(
            source_domain='hadith',
            work_slug=self.config.collection_slug,
            source_id=self.config.collection_source_id,
            display_name=collection_name,
            citation_label=self.config.citation_label,
            author_name=self.config.author_name,
            language_code=self.config.language_code,
            source_kind='hadith_collection',
            upstream_provider=self.config.upstream_provider,
            upstream_resource_id=None,
            enabled=self.config.enabled,
            approved_for_answering=self.config.approved_for_answering,
            priority_rank=self.config.priority_rank,
            version_label=self.config.version_label,
            policy_note=self.config.policy_note,
            metadata_json={
                'bootstrap': False,
                'dataset_format': 'meeatif/hadith_datasets_enriched_v2',
                'enrichment_version': 'v2',
                'citation_quality': {
                    'collection_number': 'hadith_global_num_direct',
                    'book_hadith': 'in_book_reference_parsed',
                },
                'collection_name': collection_name,
                'structure_assessment': {
                    'book_layer': 'kitab_num_direct',
                    'chapter_layer': 'synthetic_baab_label_enriched',
                },
                'arabic_text_source': 'joined_from_original_json' if arabic_lookup else 'not_available',
                'arabic_text_coverage': f'{len(arabic_lookup)}/{len(payload)}' if arabic_lookup else '0/0',
            },
        )

        books_by_number: dict[int, NormalizedHadithBook] = {}
        entries: list[NormalizedHadithEntry] = []
        notes: list[str] = []
        stubs_skipped = 0
        arabic_joined = 0
        arabic_missing = 0

        for index, row in enumerate(payload, start=1):
            if not isinstance(row, dict):
                notes.append(f'invalid_row_type_row:{index}')
                continue

            # --- Skip stubs entirely ---
            if row.get('is_stub'):
                stubs_skipped += 1
                continue

            # --- Extract hadith number ---
            hadith_global_num = row.get('hadith_global_num')
            if hadith_global_num is None:
                hadith_id = _clean(row.get('hadith_id'))
                hadith_global_num = _parse_hadith_number_from_id(hadith_id)
            if hadith_global_num is None:
                notes.append(f'missing_hadith_number_row:{index}')
                continue
            collection_hadith_number = int(hadith_global_num)

            # --- Parse in-book reference ---
            in_book_text = _clean(row.get('in_book_reference'))
            parsed_in_book = _parse_in_book_reference(in_book_text)
            if parsed_in_book is None:
                notes.append(f'missing_in_book_reference_for_collection:{collection_hadith_number}')
                continue
            book_number, in_book_hadith_number = parsed_in_book

            # --- Book (kitab) ---
            kitab_num = int(row.get('kitab_num') or book_number)
            kitab_title_en = _clean(row.get('kitab_title_english'))
            kitab_title_ar = _clean(row.get('kitab_title_arabic'))

            if kitab_num not in books_by_number:
                books_by_number[kitab_num] = NormalizedHadithBook(
                    collection_source_id=self.config.collection_source_id,
                    canonical_book_id=f'hadith:{self.config.collection_slug}:book:{kitab_num}',
                    book_number=kitab_num,
                    upstream_book_id=kitab_num,
                    title_en=kitab_title_en or f'Book {kitab_num}',
                    title_ar=kitab_title_ar,
                    metadata_json={
                        'title_role': 'kitab_title',
                        'source_dataset': 'meeatif/hadith_datasets_enriched_v2',
                        'kitab_domain': list(row.get('kitab_domain') or []),
                        'kitab_range_start': row.get('kitab_range_start'),
                        'kitab_range_end': row.get('kitab_range_end'),
                        'collection_name': collection_name,
                    },
                )

            # --- Canonical refs (transform bukhari:N → hadith:sahih-al-bukhari-en:N) ---
            canonical_ref_collection = f'hadith:{self.config.collection_slug}:{collection_hadith_number}'
            canonical_book_id = f'hadith:{self.config.collection_slug}:book:{kitab_num}'

            # --- Text fields ---
            narrator = _clean(row.get('narrator'))
            matn_text = _clean(row.get('matn_text'))
            full_text = _clean(row.get('full_text'))
            reference_url = _clean(row.get('reference_url'))

            # --- Arabic text (joined from original JSON) ---
            arabic_text = arabic_lookup.get(collection_hadith_number)
            if arabic_text:
                arabic_joined += 1
            else:
                arabic_missing += 1

            # --- Enrichment metadata ---
            enrichment_metadata: dict[str, Any] = {
                'source_dataset': 'meeatif/hadith_datasets_enriched_v2',
                'enrichment_version': 'v2',
                'reference_url': reference_url,
                'public_collection_number': collection_hadith_number,
                'in_book_reference_text': in_book_text,
                'in_book_book_number': book_number,
                'in_book_hadith_number': in_book_hadith_number,
                'collection_name': collection_name,
                'numbering_quality': 'hadith_global_num_direct',
                'book_title_en': kitab_title_en,
                'book_title_ar': kitab_title_ar,
                # Enrichment-specific fields
                'kitab_domain': list(row.get('kitab_domain') or []),
                'query_family': _clean(row.get('query_family')),
                'synthetic_baab_label': _clean(row.get('synthetic_baab_label')),
                'synthetic_baab_id': _clean(row.get('synthetic_baab_id')),
                'has_direct_prophetic_statement': bool(row.get('has_direct_prophetic_statement')),
                'is_range_ref': bool(row.get('is_range_ref')),
                'kitab_range_start': row.get('kitab_range_start'),
                'kitab_range_end': row.get('kitab_range_end'),
                'arabic_text_source': 'joined_from_original_json' if arabic_text else 'not_available',
            }

            entries.append(
                NormalizedHadithEntry(
                    collection_source_id=self.config.collection_source_id,
                    canonical_entry_id=canonical_ref_collection,
                    canonical_ref_collection=canonical_ref_collection,
                    canonical_ref_book_hadith=f'hadith:{self.config.collection_slug}:book:{kitab_num}:hadith:{in_book_hadith_number}',
                    canonical_ref_book_chapter_hadith=None,
                    collection_slug=self.config.collection_slug,
                    collection_hadith_number=collection_hadith_number,
                    in_book_hadith_number=in_book_hadith_number,
                    book_number=kitab_num,
                    chapter_number=None,
                    canonical_book_id=canonical_book_id,
                    canonical_chapter_id=None,
                    upstream_entry_id=collection_hadith_number,
                    upstream_book_id=kitab_num,
                    upstream_chapter_id=None,
                    english_narrator=narrator,
                    english_text=full_text,
                    arabic_text=arabic_text,
                    narrator_chain_text=narrator,
                    matn_text=matn_text,
                    grading=_normalize_grade(_clean(row.get('grade'))),
                    metadata_json=enrichment_metadata,
                    raw_json=row,
                )
            )

        books = sorted(books_by_number.values(), key=lambda item: item.book_number)
        notes.append(f'stubs_skipped:{stubs_skipped}')
        notes.append(f'arabic_joined:{arabic_joined}')
        notes.append(f'arabic_missing:{arabic_missing}')
        notes.append(f'has_direct_prophetic_statement_count:{sum(1 for e in entries if e.metadata_json.get("has_direct_prophetic_statement"))}')

        manifest = HadithIngestionManifest(
            collection_source_id=self.config.collection_source_id,
            work_slug=self.config.collection_slug,
            language_code=self.config.language_code,
            expected_books=len(books),
            expected_entries=len(entries),
            numbering_scheme='hadith_global_num_direct',
            notes=list(notes),
        )
        return HadithCollectionBatch(
            collection_seed=collection_seed,
            books=books,
            chapters=[],
            entries=entries,
            manifest=manifest,
            notes=notes,
        )
