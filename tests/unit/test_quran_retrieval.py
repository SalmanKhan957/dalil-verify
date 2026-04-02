from services.quran_retrieval.fetcher import fetch_quran_span
from services.quran_retrieval.metadata_loader import load_quran_metadata


def test_load_quran_metadata_from_corpus():
    metadata = load_quran_metadata()
    assert metadata[1]["ayah_count"] == 7
    assert metadata[94]["ayah_count"] == 8
    assert metadata[112]["ayah_count"] == 4
    assert metadata[94]["surah_name_ar"] == "الشرح"
    assert metadata[94]["surah_name_en"] == "ash-sharh"


def test_fetch_single_ayah_quran_span():
    result = fetch_quran_span(surah_no=94, ayah_start=5, ayah_end=5)
    assert result["canonical_source_id"] == "quran:94:5"
    assert result["citation_string"] == "Quran 94:5"
    assert result["arabic_text"] == "فَإِنَّ مَعَ الْعُسْرِ يُسْرًا"
    assert result["translation"]["translation_name"] == "Towards Understanding the Quran"
    assert result["translation"]["text"] == "Indeed, there is ease with hardship."
    assert len(result["ayah_rows"]) == 1
    assert result["ayah_rows"][0]["arabic_canonical_source_id"] == "quran:94:5:ar"


def test_fetch_multi_ayah_quran_span():
    result = fetch_quran_span(surah_no=94, ayah_start=5, ayah_end=6)
    assert result["canonical_source_id"] == "quran:94:5-6"
    assert result["citation_string"] == "Quran 94:5-6"
    assert len(result["ayah_rows"]) == 2
    assert [row["ayah_no"] for row in result["ayah_rows"]] == [5, 6]
    assert "فَإِنَّ مَعَ الْعُسْرِ يُسْرًا" in result["arabic_text"]
    assert "إِنَّ مَعَ الْعُسْرِ يُسْرًا" in result["arabic_text"]
    assert "Indeed, there is ease with hardship." in result["translation"]["text"]
    assert "Most certainly, there is ease with hardship." in result["translation"]["text"]


def test_fetch_whole_surah_span():
    result = fetch_quran_span(surah_no=112, ayah_start=1, ayah_end=4)
    assert result["canonical_source_id"] == "quran:112:1-4"
    assert len(result["ayah_rows"]) == 4
    assert result["ayah_rows"][0]["citation_string"] == "Quran 112:1"
    assert result["ayah_rows"][-1]["citation_string"] == "Quran 112:4"
