from domains.hadith_topical.taxonomy import ALIAS_TO_TOPIC, TOPIC_BY_SLUG


def test_taxonomy_contains_curated_seed_topics() -> None:
    assert 'rizq' in TOPIC_BY_SLUG
    assert 'anger' in TOPIC_BY_SLUG
    assert 'lying' in TOPIC_BY_SLUG


def test_aliases_map_back_to_curated_seed_topics() -> None:
    assert ALIAS_TO_TOPIC['rizk'] == 'rizq'
    assert ALIAS_TO_TOPIC['envy'] == 'hasad'
    assert ALIAS_TO_TOPIC['intentions'] == 'sincerity'
