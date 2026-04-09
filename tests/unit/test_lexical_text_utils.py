from shared.utils.lexical import build_snippet, expand_query_tokens, field_score, normalize_search_text, tokenize_search_text, trigram_similarity


def test_normalize_and_tokenize_query_text() -> None:
    assert normalize_search_text('  Explain: Patience & Intention!  ') == 'explain: patience intention'
    assert tokenize_search_text('Explain the patience in faith') == ['patience', 'faith']


def test_expand_query_tokens_applies_curated_synonyms() -> None:
    tokens = expand_query_tokens(['niyyah', 'patience'])
    assert 'intention' in tokens
    assert 'sabr' in tokens


def test_trigram_similarity_supports_fuzzy_title_matching() -> None:
    assert trigram_similarity('revalation', 'revelation') > 0.45


def test_field_score_rewards_exact_phrase_and_token_overlap() -> None:
    score = field_score(
        query_text='ease after hardship',
        query_tokens=['ease', 'hardship'],
        field_text='Indeed with hardship comes ease.',
        weight=1.0,
    )
    assert score.score > 0
    assert set(score.matched_terms) == {'ease', 'hardship'}


def test_build_snippet_returns_focused_excerpt() -> None:
    text = 'Faith has many branches. Patience is one of the noble qualities believers hold firmly.'
    snippet = build_snippet(text, query_text='patience')
    assert 'Patience' in snippet or 'patience' in snippet
    assert len(snippet) <= 221
