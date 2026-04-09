from __future__ import annotations

from domains.hadith_topical.contracts import HadithTopicalQuery


def build_hadith_topical_bm25_query(
    query: HadithTopicalQuery,
    *,
    collection_source_id: str | None = None,
    size: int = 50,
) -> dict:
    should = []
    if query.normalized_query:
        should.append({"match_phrase": {"chapter_title_en": {"query": query.normalized_query, "boost": 4.2}}})
        should.append({"match": {"chapter_title_en": {"query": query.normalized_query, "boost": 3.1}}})
        should.append({"match": {"baab_plus_matn_en": {"query": query.normalized_query, "boost": 2.1}}})
        should.append({"match": {"contextual_summary": {"query": query.normalized_query, "boost": 1.4}}})
        should.append({"match": {"directive_labels_text": {"query": query.normalized_query, "boost": 1.25}}})
        should.append({"match": {"english_text": {"query": query.normalized_query, "boost": 1.0}}})
        should.append({"match": {"book_title_en": {"query": query.normalized_query, "boost": 0.65}}})
    for topic in query.topic_candidates:
        should.append({"term": {"topic_tags": {"value": topic, "boost": 2.5}}})
        should.append({"term": {"normalized_topic_terms": {"value": topic, "boost": 2.1}}})
        should.append({"term": {"moral_concepts": {"value": topic, "boost": 1.7}}})
    if query.topic_family:
        should.append({"term": {"topic_family": {"value": query.topic_family, "boost": 1.1}}})
    for bias in query.directive_biases:
        should.append({"term": {"directive_labels": {"value": bias, "boost": 1.15}}})
    filters = []
    if collection_source_id:
        filters.append({"term": {"collection_source_id": collection_source_id}})
    must_not = [
        {"term": {"incidental_topic_flags": "incidental_mention_risk"}},
    ]
    return {
        "size": int(size),
        "query": {
            "bool": {
                "filter": filters,
                "must_not": must_not,
                "should": should or [{"match_all": {}}],
                "minimum_should_match": 1,
            }
        },
        "sort": [
            "_score",
            {"answerability_score": {"order": "desc"}},
            {"central_topic_score": {"order": "desc"}},
        ],
    }
