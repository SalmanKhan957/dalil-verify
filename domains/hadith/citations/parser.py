from __future__ import annotations

import re

from domains.hadith.citations.aliases import resolve_collection_alias
from domains.hadith.contracts import HadithCitationReference
from domains.hadith.types import HadithReferenceType

_COLLECTION_SOURCE_ID = 'hadith:sahih-al-bukhari-en'
_COLLECTION_RE = re.compile(
    r'\b(?P<collection>sahih\s+al\-?bukhari|sahih\s+bukhari|bukhari|imam\s+bukhari)\b',
    re.IGNORECASE,
)
_BOOK_CHAPTER_HADITH_RE = re.compile(
    r'\bbook\s*(?P<book>\d{1,3})\s*(?:,|:)?\s*chapter\s*(?P<chapter>\d{1,4})\s*(?:,|:)?\s*(?:hadith|no\.?|number)?\s*(?P<hadith>\d{1,5})\b',
    re.IGNORECASE,
)
_BOOK_HADITH_RE = re.compile(
    r'\bbook\s*(?P<book>\d{1,3})\s*(?:,|:)?\s*(?:hadith|no\.?|number)?\s*(?P<hadith>\d{1,5})\b',
    re.IGNORECASE,
)
_COMPACT_REF_RE = re.compile(r'\b(?P<book>\d{1,3})\s*[:\-]\s*(?P<hadith>\d{1,5})\b')
_COLLECTION_NUMBER_RE = re.compile(r'\b(?:hadith|no\.?|number)?\s*(?P<number>\d{1,5})\b', re.IGNORECASE)


def parse_hadith_citation(query: str) -> HadithCitationReference | None:
    text = ' '.join((query or '').split())
    if not text:
        return None

    collection_match = _COLLECTION_RE.search(text)
    if not collection_match:
        return None

    collection_slug = resolve_collection_alias(collection_match.group('collection') or '')
    if collection_slug is None:
        return None

    tail = text[collection_match.end():].strip(' ,:-')

    chapter_match = _BOOK_CHAPTER_HADITH_RE.search(tail)
    if chapter_match:
        book_number = int(chapter_match.group('book'))
        chapter_number = int(chapter_match.group('chapter'))
        hadith_number = chapter_match.group('hadith')
        return HadithCitationReference(
            collection_slug=collection_slug,
            collection_source_id=_COLLECTION_SOURCE_ID,
            reference_type=HadithReferenceType.BOOK_CHAPTER_AND_HADITH,
            canonical_ref=f'hadith:{collection_slug}:book:{book_number}:chapter:{chapter_number}:hadith:{hadith_number}',
            hadith_number=hadith_number,
            book_number=book_number,
            chapter_number=chapter_number,
            original_query=query,
        )

    book_match = _BOOK_HADITH_RE.search(tail) or _COMPACT_REF_RE.search(tail)
    if book_match:
        book_number = int(book_match.group('book'))
        hadith_number = book_match.group('hadith')
        return HadithCitationReference(
            collection_slug=collection_slug,
            collection_source_id=_COLLECTION_SOURCE_ID,
            reference_type=HadithReferenceType.BOOK_AND_HADITH,
            canonical_ref=f'hadith:{collection_slug}:book:{book_number}:hadith:{hadith_number}',
            hadith_number=hadith_number,
            book_number=book_number,
            original_query=query,
        )

    number_match = _COLLECTION_NUMBER_RE.search(tail)
    if number_match:
        hadith_number = number_match.group('number')
        return HadithCitationReference(
            collection_slug=collection_slug,
            collection_source_id=_COLLECTION_SOURCE_ID,
            reference_type=HadithReferenceType.COLLECTION_NUMBER,
            canonical_ref=f'hadith:{collection_slug}:{hadith_number}',
            hadith_number=hadith_number,
            original_query=query,
        )
    return None
