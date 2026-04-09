from domains.hadith_topical.query_normalizer import normalize_hadith_topical_query
from infrastructure.search.opensearch.hadith_topical_queries import build_hadith_topical_bm25_query


def test_bm25_query_prioritizes_chapter_title_and_baab_plus_matn() -> None:
    query = normalize_hadith_topical_query('Give me hadith about lying')
    payload = build_hadith_topical_bm25_query(query, collection_source_id='hadith:sahih-al-bukhari-en', size=10)
    should = payload['query']['bool']['should']
    chapter_phrase = [item for item in should if item.get('match_phrase', {}).get('chapter_title_en')]
    chapter_match = [item for item in should if item.get('match', {}).get('chapter_title_en')]
    combined_match = [item for item in should if item.get('match', {}).get('baab_plus_matn_en')]

    assert chapter_phrase
    assert chapter_phrase[0]['match_phrase']['chapter_title_en']['boost'] >= 4.0
    assert chapter_match
    assert chapter_match[0]['match']['chapter_title_en']['boost'] >= 3.0
    assert combined_match
