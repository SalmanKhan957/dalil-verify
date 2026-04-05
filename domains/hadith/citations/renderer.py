from __future__ import annotations

from domains.hadith.contracts import HadithCitationReference
from domains.hadith.types import HadithReferenceType

_COLLECTION_LABELS = {'sahih-al-bukhari-en': 'Sahih al-Bukhari'}


def render_hadith_citation(reference: HadithCitationReference) -> str:
    label = _COLLECTION_LABELS.get(reference.collection_slug, reference.collection_slug)
    if reference.reference_type == HadithReferenceType.BOOK_CHAPTER_AND_HADITH:
        return f'{label}, Book {reference.book_number}, Chapter {reference.chapter_number}, Hadith {reference.hadith_number}'
    if reference.reference_type == HadithReferenceType.BOOK_AND_HADITH:
        return f'{label}, Book {reference.book_number}, Hadith {reference.hadith_number}'
    return f'{label}, Hadith {reference.hadith_number}'
