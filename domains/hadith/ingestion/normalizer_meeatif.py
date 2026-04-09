from __future__ import annotations

import re
from dataclasses import dataclass
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

_REFERENCE_RE = re.compile(r"(?i)(?:^|/)bukhari:(\d+)(?:$|[/?#])")
_IN_BOOK_REF_RE = re.compile(r"(?i)book\s+(\d+)\s*,\s*hadith\s+(\d+)")
_NARRATOR_SPLIT_RE = re.compile(r"^(Narrated\s+[^:]{1,220}:)\s*(.+)$", re.IGNORECASE | re.DOTALL)


@dataclass(slots=True)
class MeeAtifHadithNormalizerConfig:
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
    version_label: str | None = 'meeatif-bukhari-v2'
    policy_note: str | None = (
        'MeeAtif/hadith_datasets ingested as the primary public citation source for Sahih al-Bukhari. '
        'Collection numbers are derived from Sunnah reference URLs and in-book references are parsed from the dataset. '
        'This source improves citation integrity for explicit lookup, but it does not provide true per-Baab topical structure.'
    )


class MeeAtifHadithCollectionNormalizer:
    """Normalize the MeeAtif Bukhari dataset into DALIL canonical contracts.

    Important: the dataset's `Chapter_Number` / `Chapter_Title_*` pair behaves like the
    macro in-book kitab layer rather than a true Baab/Tarjamah hierarchy. We therefore
    model it as the canonical book layer and do not synthesize a fake chapter layer.
    """

    def __init__(self, *, config: MeeAtifHadithNormalizerConfig | None = None) -> None:
        self.config = config or MeeAtifHadithNormalizerConfig()

    def normalize(self, payload: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> HadithCollectionBatch:
        if not isinstance(payload, list):
            raise TypeError('meeatif_hadith_payload_must_be_list')
        if not payload:
            raise ValueError('meeatif_hadith_payload_empty')

        collection_name = _clean_optional_text(payload[0].get('Book')) or self.config.display_name
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
                'dataset_format': 'meeatif/hadith_datasets',
                'citation_quality': {
                    'collection_number': 'reference_url_linked',
                    'book_hadith': 'in_book_reference_linked',
                },
                'collection_name': collection_name,
                'structure_assessment': {
                    'book_layer': 'parsed_from_in_book_reference_and_dataset_title_fields',
                    'chapter_layer': 'not_available_as_true_per_baab_in_source',
                },
            },
        )

        books_by_number: dict[int, NormalizedHadithBook] = {}
        entries: list[NormalizedHadithEntry] = []
        notes: list[str] = []

        for index, row in enumerate(payload, start=1):
            if not isinstance(row, dict):
                notes.append(f'invalid_row_type_row:{index}')
                continue

            reference_url = _clean_optional_text(row.get('Reference'))
            collection_hadith_number = _parse_collection_hadith_number(reference_url)
            if collection_hadith_number is None:
                notes.append(f'missing_collection_reference_row:{index}')
                continue

            in_book_reference_text = _clean_optional_text(row.get('In-book reference'))
            parsed_in_book = _parse_in_book_reference(in_book_reference_text)
            if parsed_in_book is None:
                notes.append(f'missing_in_book_reference_for_collection:{collection_hadith_number}')
                continue
            book_number, in_book_hadith_number = parsed_in_book

            kitab_title_en_raw = _clean_optional_text(row.get('Chapter_Title_English'))
            kitab_title_ar_raw = _clean_optional_text(row.get('Chapter_Title_Arabic'))
            kitab_title_en = _normalize_meeatif_title_en(kitab_title_en_raw)
            kitab_title_ar = _normalize_meeatif_title_ar(kitab_title_ar_raw)
            english_text_full = _clean_optional_text(row.get('English_Text'))
            arabic_text = _clean_optional_text(row.get('Arabic_Text'))
            grade_text = _clean_optional_text(row.get('Grade'))
            narrator, english_text = _split_narrator_and_matn(english_text_full)

            if book_number not in books_by_number:
                books_by_number[book_number] = NormalizedHadithBook(
                    collection_source_id=self.config.collection_source_id,
                    canonical_book_id=f'hadith:{self.config.collection_slug}:book:{book_number}',
                    book_number=book_number,
                    upstream_book_id=book_number,
                    title_en=kitab_title_en or f'Book {book_number}',
                    title_ar=kitab_title_ar,
                    metadata_json={
                        'title_role': 'kitab_title',
                        'source_dataset_field_en': 'Chapter_Title_English',
                        'source_dataset_field_ar': 'Chapter_Title_Arabic',
                        'collection_name': collection_name,
                        'in_book_reference_example': in_book_reference_text,
                    },
                )

            canonical_ref_collection = f'hadith:{self.config.collection_slug}:{collection_hadith_number}'
            canonical_book_id = f'hadith:{self.config.collection_slug}:book:{book_number}'
            entries.append(
                NormalizedHadithEntry(
                    collection_source_id=self.config.collection_source_id,
                    canonical_entry_id=canonical_ref_collection,
                    canonical_ref_collection=canonical_ref_collection,
                    canonical_ref_book_hadith=f'hadith:{self.config.collection_slug}:book:{book_number}:hadith:{in_book_hadith_number}',
                    canonical_ref_book_chapter_hadith=None,
                    collection_slug=self.config.collection_slug,
                    collection_hadith_number=collection_hadith_number,
                    in_book_hadith_number=in_book_hadith_number,
                    book_number=book_number,
                    chapter_number=None,
                    canonical_book_id=canonical_book_id,
                    canonical_chapter_id=None,
                    upstream_entry_id=collection_hadith_number,
                    upstream_book_id=book_number,
                    upstream_chapter_id=None,
                    english_narrator=narrator,
                    english_text=english_text,
                    arabic_text=arabic_text,
                    narrator_chain_text=narrator,
                    matn_text=english_text,
                    grading=_normalize_grade(grade_text),
                    metadata_json={
                        'source_dataset': 'meeatif/hadith_datasets',
                        'reference_url': reference_url,
                        'public_collection_number': collection_hadith_number,
                        'in_book_reference_text': in_book_reference_text,
                        'in_book_book_number': book_number,
                        'in_book_hadith_number': in_book_hadith_number,
                        'collection_name': collection_name,
                        'numbering_quality': 'reference_url_linked',
                        'book_title_en': kitab_title_en,
                        'book_title_ar': kitab_title_ar,
                        'book_title_en_raw': kitab_title_en_raw,
                        'book_title_ar_raw': kitab_title_ar_raw,
                        'source_structure_note': 'dataset provides collection + kitab-level title + matn, not true per-baab hierarchy',
                    },
                    raw_json=row,
                )
            )

        books = sorted(books_by_number.values(), key=lambda item: item.book_number)
        manifest = HadithIngestionManifest(
            collection_source_id=self.config.collection_source_id,
            work_slug=self.config.collection_slug,
            language_code=self.config.language_code,
            expected_books=len(books),
            expected_entries=len(entries),
            numbering_scheme='collection_number_reference_url_linked',
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


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_collection_hadith_number(reference_url: str | None) -> int | None:
    if not reference_url:
        return None
    match = _REFERENCE_RE.search(reference_url.strip())
    if not match:
        return None
    return int(match.group(1))


def _parse_in_book_reference(in_book_reference_text: str | None) -> tuple[int, int] | None:
    if not in_book_reference_text:
        return None
    match = _IN_BOOK_REF_RE.search(in_book_reference_text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _split_narrator_and_matn(english_text_full: str | None) -> tuple[str | None, str | None]:
    text = _clean_optional_text(english_text_full)
    if text is None:
        return None, None
    match = _NARRATOR_SPLIT_RE.match(text)
    if not match:
        return None, text
    narrator = _clean_optional_text(match.group(1))
    matn = _clean_optional_text(match.group(2))
    return narrator, matn or text


def _normalize_grade(grade_text: str | None) -> NormalizedHadithGrading | None:
    text = _clean_optional_text(grade_text)
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
        provenance_note='Imported from MeeAtif/hadith_datasets row grade field.',
        metadata_json={'source_dataset': 'meeatif/hadith_datasets'},
    )


def _normalize_meeatif_title_en(value: str | None) -> str | None:
    text = _clean_optional_text(value)
    if not text:
        return None
    normalized = ' '.join(text.split()).strip()
    lower = normalized.lower()
    if lower in {'chapter', 'chapter:'}:
        return None
    return normalized


def _normalize_meeatif_title_ar(value: str | None) -> str | None:
    text = _clean_optional_text(value)
    if not text:
        return None
    normalized = ' '.join(text.split()).strip()
    if normalized in {'باب', 'باب:'}:
        return None
    return normalized
