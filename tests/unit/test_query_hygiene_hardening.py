from domains.ask.topical_query import detect_topical_query_intent
from domains.query_intelligence.concept_linker import link_query_to_concepts
from domains.query_intelligence.normalization import normalize_user_query
from domains.query_intelligence.query_family_classifier import classify_query_family


def test_normalize_user_query_splits_compact_reference_and_folds_prophet_honorifics() -> None:
    assert normalize_user_query('bukari7277 what did Prophet ﷺ say abt rizk?') == 'bukhari 7277 what did the prophet say about rizq'


def test_query_family_classifier_handles_noisy_prophetic_guidance_wording() -> None:
    family = classify_query_family('What did Prophet SAW say regarding anger?')
    assert family is not None
    assert family.family_id == 'hadith_prophetic_guidance'
    assert family.domain == 'hadith'


def test_concept_linker_fuzzy_matches_jealousi_typo_to_hasad() -> None:
    concepts = link_query_to_concepts('Any hadees on jealousi?', domain='hadith')
    assert concepts
    assert concepts[0].slug == 'hasad'


def test_concept_linker_maps_prayer_to_salah_without_hardcoded_route_logic() -> None:
    concepts = link_query_to_concepts('Any hadith about prayer?', domain='hadith')
    assert concepts
    assert concepts[0].slug == 'salah'


def test_topical_detector_handles_noisy_hadith_query_with_alias_and_spacing_noise() -> None:
    route = detect_topical_query_intent('plz tell me hadees about sustenance')
    assert route['route_type'] == 'topical_hadith_query'
    assert route['topic_query'] == 'sustenance'
