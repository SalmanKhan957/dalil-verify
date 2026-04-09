from domains.hadith.ingestion.normalizer_meeatif import _normalize_meeatif_title_en, _normalize_meeatif_title_ar
from domains.answer_engine.response_builder import _clean_hadith_book_title


def test_normalize_meeatif_title_en_preserves_full_heading_for_storage():
    assert _normalize_meeatif_title_en('Chapter: The Tahajjud Prayer at night') == 'Chapter: The Tahajjud Prayer at night'


def test_normalize_meeatif_title_en_drops_empty_prefix():
    assert _normalize_meeatif_title_en('Chapter:') is None


def test_normalize_meeatif_title_ar_preserves_full_heading_for_storage():
    assert _normalize_meeatif_title_ar('باب قيام الليل') == 'باب قيام الليل'


def test_clean_hadith_book_title_drops_placeholder_tokens():
    assert _clean_hadith_book_title('Chapter:', language='en') is None
    assert _clean_hadith_book_title('باب', language='ar') is None


def test_clean_hadith_book_title_strips_display_prefixes():
    assert _clean_hadith_book_title('Chapter: The Tahajjud Prayer at night', language='en') == 'The Tahajjud Prayer at night'
    assert _clean_hadith_book_title('باب قيام الليل', language='ar') == 'قيام الليل'
