from domains.ask.classifier import classify_ask_query
from domains.ask.topical_query import detect_topical_query_intent
from domains.query_intelligence.concept_linker import link_query_to_concepts
from domains.query_intelligence.query_family_classifier import classify_query_family


def test_query_family_classifier_detects_prophetic_guidance() -> None:
    family = classify_query_family('What did the Prophet ﷺ say about anger?')
    assert family is not None
    assert family.family_id == 'hadith_prophetic_guidance'
    assert family.domain == 'hadith'


def test_concept_linker_maps_jealousy_to_hasad() -> None:
    concepts = link_query_to_concepts('What did the Prophet say about jealousy?', domain='hadith')
    assert concepts
    assert concepts[0].slug == 'hasad'


def test_topical_detector_routes_prophetic_guidance_query_without_hadith_keyword() -> None:
    route = detect_topical_query_intent('What did the Prophet ﷺ say about anger?', allow_multi_source=False)
    assert route['matched'] is True
    assert route['route_type'] == 'topical_hadith_query'
    assert route['query_profile'] == 'prophetic_guidance'
    assert route['topic_query'] == 'anger'


def test_classifier_resolves_named_quran_anchor_to_explicit_reference() -> None:
    route = classify_ask_query('Explain Ayat al-Kursi with tafsir')
    assert route['route_type'] == 'explicit_quran_reference'
    assert route['reference_match_type'] == 'named_anchor'
    assert route['parsed_reference']['surah_no'] == 2
    assert route['parsed_reference']['ayah_start'] == 255


def test_classifier_marks_broad_hadith_self_improvement_query_as_needing_clarification() -> None:
    route = classify_ask_query('How can I improve myself according to hadith?')
    assert route['route_type'] == 'unsupported_for_now'
    assert route['reason'] == 'broad_hadith_topic_requires_clarification'


def test_classifier_prefers_explicit_hadith_reference_over_named_quran_anchor() -> None:
    route = classify_ask_query('Sahih al-Bukhari 20')
    assert route['route_type'] == 'explicit_hadith_reference'
    assert route['parsed_hadith_citation']['canonical_ref'] == 'hadith:sahih-al-bukhari-en:20'
