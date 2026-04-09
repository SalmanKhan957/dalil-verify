from domains.hadith_topical.contracts import HadithTopicalCandidate, HadithTopicalQuery
from domains.hadith_topical.result_selector import select_topical_candidates


def test_result_selector_prefers_high_answerability_and_centrality() -> None:
    query = HadithTopicalQuery(raw_query='anger', normalized_query='anger', topic_candidates=('anger',), query_profile='general_topic')
    strong = HadithTopicalCandidate(
        canonical_ref='hadith:1',
        source_id='hadith:sahih-al-bukhari-en',
        retrieval_origin='hybrid',
        rerank_score=0.91,
        central_topic_score=0.82,
        answerability_score=0.86,
        guidance_role='direct_moral_instruction',
        matched_topics=('anger',),
        metadata={'builder_rank_score': 0.9},
    )
    weak = HadithTopicalCandidate(
        canonical_ref='hadith:2',
        source_id='hadith:sahih-al-bukhari-en',
        retrieval_origin='hybrid',
        rerank_score=0.88,
        central_topic_score=0.46,
        answerability_score=0.31,
        incidental_topic_penalty=0.5,
        narrative_specificity_score=0.8,
        guidance_role='narrative_incident',
        metadata={'builder_rank_score': 0.22},
    )
    result = select_topical_candidates(query, [weak, strong], max_results=1)
    assert not result.abstain
    assert result.selected[0].canonical_ref == 'hadith:1'


def test_result_selector_abstains_when_no_candidate_passes_threshold() -> None:
    query = HadithTopicalQuery(raw_query='anger', normalized_query='anger', topic_candidates=('anger',), query_profile='general_topic')
    weak = HadithTopicalCandidate(
        canonical_ref='hadith:2',
        source_id='hadith:sahih-al-bukhari-en',
        retrieval_origin='hybrid',
        rerank_score=0.42,
        central_topic_score=0.12,
        answerability_score=0.2,
        metadata={'builder_rank_score': 0.18},
    )
    result = select_topical_candidates(query, [weak], max_results=1)
    assert result.abstain


def test_result_selector_rejects_narrative_incident_for_prophetic_guidance_query() -> None:
    query = HadithTopicalQuery(raw_query='What did the Prophet say about anger?', normalized_query='anger', topic_candidates=('anger',), query_profile='prophetic_guidance')
    weak_narrative = HadithTopicalCandidate(
        canonical_ref='hadith:2',
        source_id='hadith:sahih-al-bukhari-en',
        retrieval_origin='hybrid',
        rerank_score=0.91,
        central_topic_score=0.56,
        answerability_score=0.58,
        guidance_role='narrative_incident',
        matched_topics=('anger',),
        metadata={'builder_rank_score': 0.34},
    )
    result = select_topical_candidates(query, [weak_narrative], max_results=1)
    assert result.abstain is True


def test_result_selector_dedupes_same_parent_ref() -> None:
    query = HadithTopicalQuery(raw_query='What did the Prophet say about anger?', normalized_query='anger', topic_candidates=('anger',), query_profile='prophetic_guidance')
    strong = HadithTopicalCandidate(
        canonical_ref='hadith:10',
        source_id='hadith:sahih-al-bukhari-en',
        retrieval_origin='guidance_artifact',
        rerank_score=0.9,
        central_topic_score=0.89,
        answerability_score=0.86,
        guidance_role='direct_moral_instruction',
        matched_topics=('anger',),
        metadata={'guidance_unit_id': 'hu:1', 'builder_rank_score': 0.92},
    )
    weaker_same_parent = HadithTopicalCandidate(
        canonical_ref='hadith:10',
        source_id='hadith:sahih-al-bukhari-en',
        retrieval_origin='guidance_artifact',
        rerank_score=0.75,
        central_topic_score=0.78,
        answerability_score=0.71,
        guidance_role='warning',
        matched_topics=('anger',),
        metadata={'guidance_unit_id': 'hu:2', 'builder_rank_score': 0.7},
    )
    result = select_topical_candidates(query, [strong, weaker_same_parent], max_results=5)
    assert not result.abstain
    assert len(result.selected) == 1
    assert result.selected[0].metadata.get('guidance_unit_id') == 'hu:1'
