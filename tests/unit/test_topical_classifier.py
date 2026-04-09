from domains.ask.classifier import classify_ask_query
from domains.ask.topical_query import detect_topical_query_intent


def test_detect_topical_hadith_query() -> None:
    route = detect_topical_query_intent('Any hadith about intention?')
    assert route['route_type'] == 'topical_hadith_query'
    assert route['action_type'] == 'explain'
    assert route['topic_query'] == 'intention'


def test_detect_topical_tafsir_query() -> None:
    route = detect_topical_query_intent('What does the Quran say about patience?')
    assert route['route_type'] == 'topical_tafsir_query'
    assert route['topic_query'] == 'patience'


def test_detect_topical_multi_source_query() -> None:
    route = detect_topical_query_intent('What does Islam say about patience?')
    assert route['route_type'] == 'topical_multi_source_query'
    assert route['topic_query'] == 'patience'


def test_public_classifier_does_not_broaden_to_topical_routes_yet() -> None:
    route = classify_ask_query('What does Islam say about patience?')
    assert route['route_type'] == 'unsupported_for_now'


def test_explicit_reference_beats_topical_pattern() -> None:
    route = classify_ask_query('What does 2:255 say about patience?')
    assert route['route_type'] == 'explicit_quran_reference'



def test_detect_topical_hadith_query_after_query_normalization() -> None:
    route = detect_topical_query_intent('Gve ahadith about rizk')
    assert route['route_type'] == 'topical_hadith_query'
    assert route['topic_query'] == 'rizq'


def test_classifier_routes_noisy_topical_hadith_query() -> None:
    route = classify_ask_query('Gve ahadith about rizk')
    assert route['route_type'] == 'topical_hadith_query'
    assert route['topic_query'] == 'rizq'
