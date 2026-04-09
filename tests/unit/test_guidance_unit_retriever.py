from __future__ import annotations

import json
from pathlib import Path

from domains.hadith_topical.guidance_unit_retriever import HadithGuidanceUnitRetriever
from domains.hadith_topical.query_normalizer import normalize_hadith_topical_query


def test_guidance_unit_retriever_prefers_direct_guidance_from_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / 'guidance_units.v1.jsonl'
    docs = [
        {
            'guidance_unit_id': 'hu:bukhari:1',
            'parent_hadith_ref': 'hadith:sahih-al-bukhari-en:10',
            'collection_source_id': 'hadith:sahih-al-bukhari-en',
            'span_text': 'The Prophet said: Do not get angry.',
            'summary_text': 'Direct guidance against anger.',
            'guidance_role': 'direct_moral_instruction',
            'topic_family': 'ethics',
            'central_concept_ids': ['anger'],
            'secondary_concept_ids': [],
            'directness_score': 0.92,
            'answerability_score': 0.88,
            'narrative_penalty': 0.01,
            'metadata': {'builder_rank_score': 0.92},
        },
        {
            'guidance_unit_id': 'hu:bukhari:2',
            'parent_hadith_ref': 'hadith:sahih-al-bukhari-en:2620',
            'collection_source_id': 'hadith:sahih-al-bukhari-en',
            'span_text': 'A long narrative mentioning that someone became angry during a treaty discussion.',
            'summary_text': 'Narrative context with incidental anger mention.',
            'guidance_role': 'narrative_context',
            'topic_family': 'ethics',
            'central_concept_ids': [],
            'secondary_concept_ids': ['anger'],
            'directness_score': 0.34,
            'answerability_score': 0.31,
            'narrative_penalty': 0.62,
            'metadata': {'builder_rank_score': 0.28},
        },
    ]
    artifact.write_text('\n'.join(json.dumps(item) for item in docs), encoding='utf-8')
    retriever = HadithGuidanceUnitRetriever(artifact_path=artifact)
    query = normalize_hadith_topical_query('What did the Prophet say about anger?')
    candidates, debug = retriever.retrieve(query=query, collection_source_id='hadith:sahih-al-bukhari-en', limit=5)
    assert candidates
    assert candidates[0].canonical_ref == 'hadith:sahih-al-bukhari-en:10'
    assert candidates[0].metadata.get('guidance_unit_id') == 'hu:bukhari:1'
    assert debug['artifact_candidate_count'] >= 1


def test_guidance_unit_retriever_keeps_best_unit_per_parent(tmp_path: Path) -> None:
    artifact = tmp_path / 'guidance_units.v1.jsonl'
    docs = [
        {
            'guidance_unit_id': 'hu:bukhari:1',
            'parent_hadith_ref': 'hadith:sahih-al-bukhari-en:10',
            'collection_source_id': 'hadith:sahih-al-bukhari-en',
            'span_text': 'The Prophet said: Do not get angry.',
            'summary_text': 'Direct guidance against anger.',
            'guidance_role': 'direct_moral_instruction',
            'topic_family': 'ethics',
            'central_concept_ids': ['anger'],
            'secondary_concept_ids': [],
            'directness_score': 0.92,
            'answerability_score': 0.88,
            'narrative_penalty': 0.01,
            'metadata': {'builder_rank_score': 0.92},
        },
        {
            'guidance_unit_id': 'hu:bukhari:1b',
            'parent_hadith_ref': 'hadith:sahih-al-bukhari-en:10',
            'collection_source_id': 'hadith:sahih-al-bukhari-en',
            'span_text': 'Someone became angry during a long story.',
            'summary_text': 'Incidental anger mention.',
            'guidance_role': 'narrative_context',
            'topic_family': 'ethics',
            'central_concept_ids': [],
            'secondary_concept_ids': ['anger'],
            'directness_score': 0.25,
            'answerability_score': 0.22,
            'narrative_penalty': 0.7,
            'metadata': {'builder_rank_score': 0.22},
        },
    ]
    artifact.write_text('\n'.join(json.dumps(item) for item in docs), encoding='utf-8')
    retriever = HadithGuidanceUnitRetriever(artifact_path=artifact)
    query = normalize_hadith_topical_query('What did the Prophet say about anger?')
    candidates, _debug = retriever.retrieve(query=query, collection_source_id='hadith:sahih-al-bukhari-en', limit=5)
    assert len(candidates) == 1
    assert candidates[0].metadata.get('guidance_unit_id') == 'hu:bukhari:1'
