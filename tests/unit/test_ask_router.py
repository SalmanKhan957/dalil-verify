from __future__ import annotations

from domains.ask.classifier import classify_ask_query
from domains.ask.route_types import AskActionType, AskRouteType


def test_routes_embedded_numeric_reference_question() -> None:
    result = classify_ask_query("What does 94:5-6 say?")
    assert result["route_type"] == AskRouteType.EXPLICIT_QURAN_REFERENCE.value
    assert result["action_type"] in {
        AskActionType.EXPLAIN.value,
        AskActionType.FETCH_TEXT.value,
    }
    assert result["reference_text"] == "94:5-6"


def test_routes_ayah_of_surah_reference() -> None:
    result = classify_ask_query("Can you explain ayah 255 of Surah Baqarah?")
    assert result["route_type"] == AskRouteType.EXPLICIT_QURAN_REFERENCE.value
    assert result["reference_text"] == "surah baqarah 255"


def test_routes_surah_name_reference() -> None:
    result = classify_ask_query("Tafsir of Surah Ikhlas")
    assert result["route_type"] == AskRouteType.EXPLICIT_QURAN_REFERENCE.value
    assert result["reference_text"] == "surah ikhlas"
    assert result["action_type"] == AskActionType.EXPLAIN.value


def test_routes_arabic_quote_with_verification_question() -> None:
    query = "إِنَّ الَّذِينَ لَا يَرْجُونَ لِقَاءَنَا وَرَضُوا بِالْحَيَاةِ الدُّنْيَا is this true?"
    result = classify_ask_query(query)
    assert result["route_type"] == AskRouteType.ARABIC_QURAN_QUOTE.value
    assert result["action_type"] == AskActionType.VERIFY_SOURCE.value
    assert "إِنَّ الَّذِينَ" in result["quote_payload"]


def test_routes_arabic_quote_with_explain_question() -> None:
    query = "إِنَّ الَّذِينَ لَا يَرْجُونَ لِقَاءَنَا what does this mean?"
    result = classify_ask_query(query)
    assert result["route_type"] == AskRouteType.ARABIC_QURAN_QUOTE.value
    assert result["action_type"] == AskActionType.VERIFY_THEN_EXPLAIN.value


def test_unsupported_generic_topic_question() -> None:
    result = classify_ask_query("What does Islam say about anxiety?")
    assert result["route_type"] == AskRouteType.UNSUPPORTED_FOR_NOW.value
