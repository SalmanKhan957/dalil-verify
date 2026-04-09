from domains.hadith.ingestion.normalizer_meeatif import _normalize_meeatif_title_en, _normalize_meeatif_title_ar
from domains.answer_engine.response_builder import _clean_hadith_book_title


def test_normalize_meeatif_title_en_strips_prefix():
    assert _normalize_meeatif_title_en('Chapter: The Tahajjud Prayer at night') == 'The Tahajjud Prayer at night'


def test_normalize_meeatif_title_en_drops_empty_prefix():
    assert _normalize_meeatif_title_en('Chapter:') is None


def test_normalize_meeatif_title_ar_strips_prefix():
    assert _normalize_meeatif_title_ar('باب قيام الليل') == 'قيام الليل'


def test_clean_hadith_book_title_drops_placeholder_tokens():
    assert _clean_hadith_book_title('Chapter:', language='en') is None
    assert _clean_hadith_book_title('باب', language='ar') is None
