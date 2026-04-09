from domains.query_intelligence.concept_linker import link_query_to_concepts


def test_artifact_strict_mode_does_not_match_lie_inside_other_words() -> None:
    matches = link_query_to_concepts(
        'The man spoke about qualities and good living during the journey.',
        domain='hadith',
        matching_mode='artifact_strict',
        max_results=4,
    )
    assert all(match.slug != 'lying' for match in matches)


def test_query_mode_still_maps_broad_hadith_question_to_patience() -> None:
    matches = link_query_to_concepts(
        'What did prophet SAW say about being patient in hardships?',
        domain='hadith',
        matching_mode='query',
        max_results=4,
    )
    assert any(match.slug == 'patience' for match in matches)
