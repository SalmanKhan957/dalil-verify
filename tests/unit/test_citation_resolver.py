from services.citation_resolver.resolver import resolve_quran_reference


QURAN_METADATA = {
    2: {"ayah_count": 286, "surah_name_en": "Al-Baqarah"},
    67: {"ayah_count": 30, "surah_name_en": "Al-Mulk"},
    94: {"ayah_count": 8, "surah_name_en": "Ash-Sharh"},
    112: {"ayah_count": 4, "surah_name_en": "Al-Ikhlas"},
}


def test_numeric_single_ayah_reference():
    result = resolve_quran_reference("94:5", quran_metadata=QURAN_METADATA)
    assert result["resolved"] is True
    assert result["surah_no"] == 94
    assert result["ayah_start"] == 5
    assert result["ayah_end"] == 5
    assert result["canonical_source_id"] == "quran:94:5"


def test_numeric_range_reference():
    result = resolve_quran_reference("94:5-6", quran_metadata=QURAN_METADATA)
    assert result["resolved"] is True
    assert result["surah_no"] == 94
    assert result["ayah_start"] == 5
    assert result["ayah_end"] == 6
    assert result["canonical_source_id"] == "quran:94:5-6"


def test_normalized_en_dash_range_reference():
    result = resolve_quran_reference("Explain 94:5–6", quran_metadata=QURAN_METADATA)
    assert result["resolved"] is True
    assert result["normalized_query"] == "94:5-6"
    assert result["canonical_source_id"] == "quran:94:5-6"


def test_surah_name_only_expands_to_whole_surah():
    result = resolve_quran_reference("Surah Ikhlas", quran_metadata=QURAN_METADATA)
    assert result["resolved"] is True
    assert result["surah_no"] == 112
    assert result["ayah_start"] == 1
    assert result["ayah_end"] == 4
    assert result["canonical_source_id"] == "quran:112:1-4"


def test_surah_name_with_single_ayah():
    result = resolve_quran_reference("Surah Ash-Sharh 5", quran_metadata=QURAN_METADATA)
    assert result["resolved"] is True
    assert result["surah_no"] == 94
    assert result["ayah_start"] == 5
    assert result["ayah_end"] == 5
    assert result["canonical_source_id"] == "quran:94:5"


def test_surah_name_with_range():
    result = resolve_quran_reference("Surah Inshirah 5-6", quran_metadata=QURAN_METADATA)
    assert result["resolved"] is True
    assert result["surah_no"] == 94
    assert result["ayah_start"] == 5
    assert result["ayah_end"] == 6
    assert result["canonical_source_id"] == "quran:94:5-6"


def test_invalid_surah_number():
    result = resolve_quran_reference("115:1", quran_metadata=QURAN_METADATA)
    assert result["resolved"] is False
    assert result["error"] == "invalid_surah_number"


def test_invalid_ayah_range():
    result = resolve_quran_reference("94:99", quran_metadata=QURAN_METADATA)
    assert result["resolved"] is False
    assert result["error"] == "invalid_ayah_range"


def test_reversed_ayah_range():
    result = resolve_quran_reference("94:6-5", quran_metadata=QURAN_METADATA)
    assert result["resolved"] is False
    assert result["error"] == "reversed_ayah_range"


def test_unknown_surah_name():
    result = resolve_quran_reference("Surah FakeName 1", quran_metadata=QURAN_METADATA)
    assert result["resolved"] is False
    assert result["error"] == "could_not_parse_reference"


def test_empty_query():
    result = resolve_quran_reference("", quran_metadata=QURAN_METADATA)
    assert result["resolved"] is False
    assert result["error"] == "empty_query"