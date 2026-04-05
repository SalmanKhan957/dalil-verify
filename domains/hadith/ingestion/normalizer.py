from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.hadith.types import (
    HadithCollectionBatch,
    HadithCollectionSeed,
    HadithIngestionManifest,
    NormalizedHadithBook,
    NormalizedHadithChapter,
    NormalizedHadithEntry,
)


@dataclass(slots=True)
class HadithJsonMirrorNormalizerConfig:
    collection_slug: str = 'sahih-al-bukhari-en'
    collection_source_id: str = 'hadith:sahih-al-bukhari-en'
    display_name: str = 'Sahih al-Bukhari (English)'
    citation_label: str = 'Sahih al-Bukhari'
    author_name: str | None = 'Imam al-Bukhari'
    language_code: str = 'en'
    upstream_provider: str = 'hadith_json_mirror'
    enabled: bool = True
    approved_for_answering: bool = False
    priority_rank: int = 1000
    policy_note: str | None = 'Canonical Hadith data ingested from a bootstrap mirror. Not yet approved for public answer composition until retrieval and provenance checks are completed.'


class HadithCollectionNormalizer:
    """Normalize a hadith-json book-file payload into DALIL canonical contracts."""

    def __init__(self, *, config: HadithJsonMirrorNormalizerConfig | None = None) -> None:
        self.config = config or HadithJsonMirrorNormalizerConfig()

    def normalize(self, payload: dict[str, Any]) -> HadithCollectionBatch:
        if not isinstance(payload, dict):
            raise TypeError('hadith_payload_must_be_dict')

        if 'hadiths' not in payload or 'metadata' not in payload:
            raise ValueError('hadith_json_book_file_missing_required_keys')

        metadata = payload.get('metadata') or {}
        hadith_rows = payload.get('hadiths') or []
        chapter_rows = payload.get('chapters') or []
        upstream_book_id = int(payload.get('id') or metadata.get('id') or 1)

        english_meta = metadata.get('english') or {}
        arabic_meta = metadata.get('arabic') or {}
        english_title = str(english_meta.get('title') or self.config.display_name).strip()
        arabic_title = _clean_optional_text(arabic_meta.get('title'))
        author_name = _clean_optional_text(english_meta.get('author')) or self.config.author_name

        collection_seed = HadithCollectionSeed(
            source_domain='hadith',
            work_slug=self.config.collection_slug,
            source_id=self.config.collection_source_id,
            display_name=english_title,
            citation_label=self.config.citation_label,
            author_name=author_name,
            language_code=self.config.language_code,
            source_kind='hadith_collection',
            upstream_provider=self.config.upstream_provider,
            upstream_resource_id=None,
            enabled=self.config.enabled,
            approved_for_answering=self.config.approved_for_answering,
            priority_rank=self.config.priority_rank,
            policy_note=self.config.policy_note,
            metadata_json={
                'bootstrap': True,
                'mirror_format': 'hadith-json/book-file',
                'citation_quality': {
                    'collection_number': 'mirror_stable',
                    'book_hadith': 'bootstrap_unverified',
                    'book_chapter_hadith': 'bootstrap_unverified',
                },
                'metadata': metadata,
            },
        )

        canonical_book_id = f'hadith:{self.config.collection_slug}:book:{upstream_book_id}'
        books = [
            NormalizedHadithBook(
                collection_source_id=self.config.collection_source_id,
                canonical_book_id=canonical_book_id,
                book_number=upstream_book_id,
                upstream_book_id=upstream_book_id,
                title_en=english_title,
                title_ar=arabic_title,
                metadata_json={
                    'source_layout': 'by_book',
                    'book_metadata': metadata,
                },
            )
        ]

        chapter_by_upstream_id: dict[int, NormalizedHadithChapter] = {}
        chapter_number_by_upstream_id: dict[int, int] = {}
        chapters: list[NormalizedHadithChapter] = []
        notes: list[str] = []

        for index, row in enumerate(chapter_rows, start=1):
            if not isinstance(row, dict):
                notes.append(f'invalid_chapter_row_type:{index}')
                continue
            upstream_chapter_id = int(row.get('id') or index)
            chapter_number = index
            chapter_number_by_upstream_id[upstream_chapter_id] = chapter_number
            chapter = NormalizedHadithChapter(
                collection_source_id=self.config.collection_source_id,
                canonical_book_id=canonical_book_id,
                canonical_chapter_id=f'hadith:{self.config.collection_slug}:book:{upstream_book_id}:chapter:{chapter_number}',
                book_number=upstream_book_id,
                chapter_number=chapter_number,
                upstream_book_id=upstream_book_id,
                upstream_chapter_id=upstream_chapter_id,
                title_en=_clean_optional_text(row.get('english')),
                title_ar=_clean_optional_text(row.get('arabic')),
                metadata_json={'source_row': row},
            )
            chapter_by_upstream_id[upstream_chapter_id] = chapter
            chapters.append(chapter)

        entries: list[NormalizedHadithEntry] = []
        for row in hadith_rows:
            if not isinstance(row, dict):
                notes.append('invalid_hadith_row_type')
                continue
            collection_hadith_number = int(row['id'])
            in_book_hadith_number = _to_optional_int(row.get('idInBook'))
            row_book_id = int(row.get('bookId') or upstream_book_id)
            row_chapter_id = _to_optional_int(row.get('chapterId'))
            chapter_number = chapter_number_by_upstream_id.get(row_chapter_id) if row_chapter_id is not None else None
            canonical_chapter_id = (
                f'hadith:{self.config.collection_slug}:book:{row_book_id}:chapter:{chapter_number}'
                if chapter_number is not None
                else None
            )
            canonical_ref_collection = f'hadith:{self.config.collection_slug}:{collection_hadith_number}'
            canonical_ref_book_hadith = (
                f'hadith:{self.config.collection_slug}:book:{row_book_id}:hadith:{in_book_hadith_number}'
                if in_book_hadith_number is not None
                else None
            )
            canonical_ref_book_chapter_hadith = (
                f'hadith:{self.config.collection_slug}:book:{row_book_id}:chapter:{chapter_number}:hadith:{in_book_hadith_number}'
                if chapter_number is not None and in_book_hadith_number is not None
                else None
            )
            english = row.get('english') or {}
            narrator = _clean_optional_text(english.get('narrator'))
            english_text = _clean_optional_text(english.get('text'))
            arabic_text = _clean_optional_text(row.get('arabic'))
            entries.append(
                NormalizedHadithEntry(
                    collection_source_id=self.config.collection_source_id,
                    canonical_entry_id=canonical_ref_collection,
                    canonical_ref_collection=canonical_ref_collection,
                    canonical_ref_book_hadith=canonical_ref_book_hadith,
                    canonical_ref_book_chapter_hadith=canonical_ref_book_chapter_hadith,
                    collection_slug=self.config.collection_slug,
                    collection_hadith_number=collection_hadith_number,
                    in_book_hadith_number=in_book_hadith_number,
                    book_number=row_book_id,
                    chapter_number=chapter_number,
                    canonical_book_id=f'hadith:{self.config.collection_slug}:book:{row_book_id}',
                    canonical_chapter_id=canonical_chapter_id,
                    upstream_entry_id=collection_hadith_number,
                    upstream_book_id=row_book_id,
                    upstream_chapter_id=row_chapter_id,
                    english_narrator=narrator,
                    english_text=english_text,
                    arabic_text=arabic_text,
                    narrator_chain_text=narrator,
                    matn_text=english_text,
                    metadata_json={
                        'mirror_source': 'hadith-json',
                        'reference_quality': 'bootstrap_unverified' if in_book_hadith_number is not None else 'collection_number_only',
                    },
                    raw_json=row,
                )
            )
            if row_chapter_id is not None and row_chapter_id not in chapter_by_upstream_id:
                notes.append(f'missing_chapter_mapping:{row_chapter_id}')

        manifest = HadithIngestionManifest(
            collection_source_id=self.config.collection_source_id,
            work_slug=self.config.collection_slug,
            language_code=self.config.language_code,
            expected_books=1,
            expected_entries=_to_optional_int(metadata.get('length')) or len(entries),
            numbering_scheme='collection_hadith_number',
            notes=list(notes),
        )
        return HadithCollectionBatch(collection_seed=collection_seed, books=books, chapters=chapters, entries=entries, manifest=manifest, notes=notes)


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_optional_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    return int(value)
