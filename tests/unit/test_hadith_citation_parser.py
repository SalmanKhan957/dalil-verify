from domains.hadith.citations.parser import parse_hadith_citation
from domains.hadith.citations.renderer import render_hadith_citation
from domains.hadith.types import HadithReferenceType


def test_parse_collection_number_citation_for_bukhari() -> None:
    reference = parse_hadith_citation('Sahih Bukhari 52')
    assert reference is not None
    assert reference.collection_slug == 'sahih-al-bukhari-en'
    assert reference.collection_source_id == 'hadith:sahih-al-bukhari-en'
    assert reference.reference_type == HadithReferenceType.COLLECTION_NUMBER
    assert reference.hadith_number == '52'
    assert reference.canonical_ref == 'hadith:sahih-al-bukhari-en:52'
    assert render_hadith_citation(reference) == 'Sahih al-Bukhari, Hadith 52'


def test_parse_book_and_hadith_citation_for_bukhari() -> None:
    reference = parse_hadith_citation('Bukhari book 3 hadith 45')
    assert reference is not None
    assert reference.reference_type == HadithReferenceType.BOOK_AND_HADITH
    assert reference.book_number == 3
    assert reference.hadith_number == '45'
    assert reference.canonical_ref == 'hadith:sahih-al-bukhari-en:book:3:hadith:45'
    assert render_hadith_citation(reference) == 'Sahih al-Bukhari, Book 3, Hadith 45'
