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
    assert result["route_type"] == AskRouteType.POLICY_RESTRICTED_REQUEST.value


def test_routes_public_topical_hadith_query() -> None:
    result = classify_ask_query("Give me hadith about patience")
    assert result["route_type"] == AskRouteType.TOPICAL_HADITH_QUERY.value
    assert result["action_type"] == AskActionType.EXPLAIN.value
    assert result["topic_query"] == "patience"


def test_routes_public_topical_tafsir_query() -> None:
    result = classify_ask_query("What does the Quran say about patience?")
    assert result["route_type"] == AskRouteType.TOPICAL_TAFSIR_QUERY.value
    assert result["action_type"] == AskActionType.EXPLAIN.value
    assert result["topic_query"] == "patience"


def test_routes_explicit_hadith_reference() -> None:
    result = classify_ask_query("Bukhari 2")
    assert result["route_type"] == AskRouteType.EXPLICIT_HADITH_REFERENCE.value
    assert result["action_type"] == AskActionType.FETCH_TEXT.value
    assert result["parsed_hadith_citation"]["canonical_ref"] == "hadith:sahih-al-bukhari-en:2"



def test_routes_short_arabic_quran_snippet() -> None:
    result = classify_ask_query("وَوَجَدَكَ ضَالًّا فَهَدَى")
    assert result["route_type"] == AskRouteType.ARABIC_QURAN_QUOTE.value
    assert "وَوَجَدَكَ" in result["quote_payload"]


def test_routes_very_short_quranic_opening_snippet() -> None:
    result = classify_ask_query("الم")
    assert result["route_type"] == AskRouteType.ARABIC_QURAN_QUOTE.value
    assert result["quote_payload"] == "الم"


def test_routes_anchored_quran_followup_from_anchor_refs() -> None:
    result = classify_ask_query(
        "What about the second verse?",
        request_context={"anchor_refs": ["quran:112:1-4"]},
    )
    assert result["route_type"] == AskRouteType.ANCHORED_FOLLOWUP_QURAN.value
    assert result["action_type"] == AskActionType.EXPLAIN.value
    assert result["followup_quran_ref"]["canonical_ref"] == "quran:112:2"


def test_routes_anchored_tafsir_followup_from_anchor_refs() -> None:
    result = classify_ask_query(
        "What does Tafheem say?",
        request_context={
            "anchor_refs": [
                "quran:112:1-4",
                "tafsir:ibn-kathir-en:84552",
                "tafsir:maarif-al-quran-en:112:1",
                "tafsir:tafheem-al-quran-en:112:1",
            ]
        },
    )
    assert result["route_type"] == AskRouteType.ANCHORED_FOLLOWUP_TAFSIR.value
    assert result["requested_tafsir_source_ids"] == ["tafsir:tafheem-al-quran-en"]


def test_routes_anchored_hadith_followup_from_anchor_refs() -> None:
    result = classify_ask_query(
        "Summarize this hadith",
        request_context={"anchor_refs": ["hadith:sahih-al-bukhari-en:7"]},
    )
    assert result["route_type"] == AskRouteType.ANCHORED_FOLLOWUP_HADITH.value
    assert result["action_type"] == AskActionType.EXPLAIN.value
    assert result["parsed_hadith_citation"]["canonical_ref"] == "hadith:sahih-al-bukhari-en:7"
