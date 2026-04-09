from __future__ import annotations

from domains.hadith_topical.query_family_classifier import classify_hadith_topic_family
from domains.hadith_topical.query_normalizer import normalize_hadith_topical_query


def test_classifies_dajjal_as_entity_eschatology() -> None:
    query = normalize_hadith_topical_query('What did the Prophet ﷺ say about coming of Dajjal?')
    decision = classify_hadith_topic_family(query)
    assert decision.family_id == 'entity_eschatology'
    assert decision.retrieval_strategy == 'thematic_passages'
    assert decision.allow_generic_fallback is False


def test_classifies_anger_as_moral_guidance() -> None:
    query = normalize_hadith_topical_query('What did the Prophet ﷺ say about anger?')
    decision = classify_hadith_topic_family(query)
    assert decision.family_id == 'moral_guidance'
    assert decision.retrieval_strategy == 'guidance_units'
