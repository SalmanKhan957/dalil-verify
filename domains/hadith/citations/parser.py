from __future__ import annotations

import re

from domains.hadith.citations.aliases import resolve_collection_alias
from domains.hadith.contracts import HadithCitationReference
from domains.hadith.types import HadithReferenceType
from domains.query_intelligence.normalization import normalize_reference_query

_COLLECTION_SOURCE_ID = 'hadith:sahih-al-bukhari-en'
_COLLECTION_NUMBER_RE = re.compile(r'\b(?:hadith|no\.?|number)?\s*(?P<number>\d{1,5})\b', re.IGNORECASE)
_BOOK_CHAPTER_HADITH_RE = re.compile(
    r'\bbook\s*(?P<book>\d{1,3})\s*(?:,|:)?\s*chapter\s*(?P<chapter>\d{1,4})\s*(?:,|:)?\s*(?:hadith|no\.?|number)?\s*(?P<hadith>\d{1,5})\b',
    re.IGNORECASE,
)
_BOOK_HADITH_RE = re.compile(
    r'\bbook\s*(?P<book>\d{1,3})\s*(?:,|:)?\s*(?:hadith|no\.?|number)?\s*(?P<hadith>\d{1,5})\b',
    re.IGNORECASE,
)
_COMPACT_REF_RE = re.compile(r'\b(?P<book>\d{1,3})\s*[:\-]\s*(?P<hadith>\d{1,5})\b')
_LEADING_NOISE_TOKENS = {'explain', 'show', 'give', 'me', 'hadith', 'please', 'find'}
_MAX_COLLECTION_NGRAM = 4


def _extract_collection_and_tail(text: str) -> tuple[str | None, str]:
    tokens = text.split()
    if not tokens:
        return None, ''

    best: tuple[int, int, str] | None = None
    token_count = len(tokens)
    for start in range(token_count):
        if start > 0 and tokens[start - 1].casefold() not in _LEADING_NOISE_TOKENS:
            continue
        for size in range(min(_MAX_COLLECTION_NGRAM, token_count - start), 0, -1):
            candidate_tokens = tokens[start:start + size]
            if any(token.isdigit() for token in candidate_tokens):
                continue
            candidate = ' '.join(candidate_tokens)
            slug = resolve_collection_alias(candidate)
            if slug is None:
                continue
            best = (start, size, slug)
            break
        if best is not None:
            break

    if best is None:
        return None, ''

    start, size, slug = best
    tail_tokens = tokens[:start] + tokens[start + size:]
    tail = ' '.join(token for token in tail_tokens if token.casefold() not in _LEADING_NOISE_TOKENS).strip(' ,:-')
    return slug, tail


def _build_reference(*, query: str, collection_slug: str, reference_type: HadithReferenceType, hadith_number: str | None = None, book_number: int | None = None, chapter_number: int | None = None) -> HadithCitationReference:
    if reference_type == HadithReferenceType.BOOK_CHAPTER_AND_HADITH:
        canonical_ref = f'hadith:{collection_slug}:book:{book_number}:chapter:{chapter_number}:hadith:{hadith_number}'
    elif reference_type == HadithReferenceType.BOOK_AND_HADITH:
        canonical_ref = f'hadith:{collection_slug}:book:{book_number}:hadith:{hadith_number}'
    else:
        canonical_ref = f'hadith:{collection_slug}:{hadith_number}'

    return HadithCitationReference(
        collection_slug=collection_slug,
        collection_source_id=_COLLECTION_SOURCE_ID,
        reference_type=reference_type,
        canonical_ref=canonical_ref,
        hadith_number=hadith_number,
        book_number=book_number,
        chapter_number=chapter_number,
        original_query=query,
    )


def parse_hadith_citation(query: str) -> HadithCitationReference | None:
    text = normalize_reference_query(query)
    if not text:
        return None

    collection_slug, tail = _extract_collection_and_tail(text)
    if collection_slug is None:
        return None

    chapter_match = _BOOK_CHAPTER_HADITH_RE.search(tail)
    if chapter_match:
        return _build_reference(
            query=query,
            collection_slug=collection_slug,
            reference_type=HadithReferenceType.BOOK_CHAPTER_AND_HADITH,
            hadith_number=chapter_match.group('hadith'),
            book_number=int(chapter_match.group('book')),
            chapter_number=int(chapter_match.group('chapter')),
        )

    book_match = _BOOK_HADITH_RE.search(tail) or _COMPACT_REF_RE.search(tail)
    if book_match:
        return _build_reference(
            query=query,
            collection_slug=collection_slug,
            reference_type=HadithReferenceType.BOOK_AND_HADITH,
            hadith_number=book_match.group('hadith'),
            book_number=int(book_match.group('book')),
        )

    number_match = _COLLECTION_NUMBER_RE.search(tail)
    if number_match:
        return _build_reference(
            query=query,
            collection_slug=collection_slug,
            reference_type=HadithReferenceType.COLLECTION_NUMBER,
            hadith_number=number_match.group('number'),
        )
    return None
