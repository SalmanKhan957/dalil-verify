from domains.hadith_topical.query_normalizer import normalize_hadith_topical_query


def test_normalizer_maps_rizk_to_rizq_topic() -> None:
    query = normalize_hadith_topical_query('Gve ahadith about rizk')
    assert query.normalized_query == 'hadith rizq'
    assert 'rizq' in query.topic_candidates
    assert query.topic_family == 'wealth'


def test_normalizer_marks_warning_profile_and_directive_bias() -> None:
    query = normalize_hadith_topical_query('hadith about punishment of hasad')
    assert query.query_profile == 'warning'
    assert 'hasad' in query.topic_candidates
    assert 'warning' in query.directive_biases


def test_normalizer_maps_prophetic_guidance_jealousy_query() -> None:
    query = normalize_hadith_topical_query('What did the Prophet say about jealousy?')
    assert query.query_profile == 'prophetic_guidance'
    assert 'hasad' in query.topic_candidates
