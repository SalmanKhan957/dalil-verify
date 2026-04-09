from __future__ import annotations

from domains.hadith_topical.contracts import HadithTopicalQuery


def build_hadith_guidance_bm25_query(
    query: HadithTopicalQuery,
    *,
    collection_source_id: str | None = None,
    size: int = 50,
) -> dict:
    should = []
    if query.normalized_query:
        should.append({'match': {'span_text': {'query': query.normalized_query, 'boost': 1.0}}})
        should.append({'match': {'summary_text': {'query': query.normalized_query, 'boost': 1.3}}})
    for topic in query.topic_candidates:
        should.append({'term': {'central_concept_ids': {'value': topic, 'boost': 2.6}}})
        should.append({'term': {'secondary_concept_ids': {'value': topic, 'boost': 1.4}}})
    if query.topic_family:
        should.append({'term': {'topic_family': {'value': query.topic_family, 'boost': 1.15}}})
    filters = []
    if collection_source_id:
        filters.append({'term': {'collection_source_id': collection_source_id}})
    return {
        'size': int(size),
        'query': {
            'bool': {
                'filter': filters,
                'should': should or [{'match_all': {}}],
                'minimum_should_match': 1,
            }
        },
        'sort': [
            '_score',
            {'answerability_score': {'order': 'desc'}},
            {'directness_score': {'order': 'desc'}},
            {'narrative_penalty': {'order': 'asc'}},
        ],
    }
