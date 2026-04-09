from __future__ import annotations

from domains.hadith.contracts import HadithLexicalHit
from domains.hadith.types import HadithEntryRecord
from domains.hadith_topical.contracts import HadithTopicalCandidate, HadithTopicalCandidateGenerationResult
from domains.hadith_topical.search_service import HadithTopicalSearchService


class _StubCandidateGenerator:
    def __init__(self, candidates):
        self._candidates = candidates

    def generate(self, request, lexical_hits=None):
        return HadithTopicalCandidateGenerationResult(candidates=tuple(self._candidates), warnings=(), debug={'stubbed': True, 'lexical_candidate_count': len(lexical_hits or [])})


def _entry(ref: str, text: str) -> HadithEntryRecord:
    return HadithEntryRecord(
        id=1,
        work_id=1,
        book_id=1,
        chapter_id=1,
        collection_source_id='hadith:sahih-al-bukhari-en',
        canonical_entry_id=f'{ref}:entry',
        canonical_ref_collection=ref,
        canonical_ref_book_hadith=f'{ref}:book',
        canonical_ref_book_chapter_hadith=f'{ref}:chapter',
        collection_hadith_number=63,
        in_book_hadith_number=63,
        book_number=1,
        chapter_number=1,
        english_narrator='Narrated Abu Hurairah:',
        english_text=text,
        arabic_text=None,
        narrator_chain_text=None,
        matn_text=None,
        metadata_json={},
        raw_json={},
        grading=None,
    )


def test_search_service_selects_ranked_candidate_from_lexical_fallback() -> None:
    service = HadithTopicalSearchService(candidate_generator=_StubCandidateGenerator([HadithTopicalCandidate(canonical_ref='hadith:sahih-al-bukhari-en:63', source_id='hadith:sahih-al-bukhari-en', retrieval_origin='lexical_fallback', matched_terms=('patience',), central_topic_score=0.81, answerability_score=0.84, incidental_topic_penalty=0.05)]))
    result = service.search(
        raw_query='give me hadith about patience',
        collection_source_id='hadith:sahih-al-bukhari-en',
        lexical_hits=[
            HadithLexicalHit(
                entry=_entry('hadith:sahih-al-bukhari-en:63', 'Patience is a gift better and more comprehensive than anything else.'),
                display_name='Sahih al-Bukhari (English)',
                citation_label='Sahih al-Bukhari',
                book_title='Book of Patience',
                chapter_title='Patience',
                score=0.87,
                matched_terms=('patience',),
                snippet='Patience is a gift better and more comprehensive than anything else.',
                retrieval_method='python_fallback',
            )
        ],
    )

    assert result.abstain is False
    assert result.selected[0].canonical_ref == 'hadith:sahih-al-bukhari-en:63'
    assert 'patience' in result.selected[0].matched_topics
    assert result.debug['candidate_generation']['lexical_candidate_count'] == 1


def test_search_service_rejects_incidental_anger_narrative() -> None:
    service = HadithTopicalSearchService(candidate_generator=_StubCandidateGenerator([HadithTopicalCandidate(canonical_ref='hadith:sahih-al-bukhari-en:63', source_id='hadith:sahih-al-bukhari-en', retrieval_origin='lexical_fallback', matched_terms=('anger',), central_topic_score=0.65, answerability_score=0.62, incidental_topic_penalty=0.7)]))
    result = service.search(
        raw_query='give hadith about anger',
        collection_source_id='hadith:sahih-al-bukhari-en',
        lexical_hits=[
            HadithLexicalHit(
                entry=_entry('hadith:sahih-al-bukhari-en:63', 'A man said to the Prophet I will be hard in questioning so do not get angry and then asked about prayer and zakat.'),
                display_name='Sahih al-Bukhari (English)',
                citation_label='Sahih al-Bukhari',
                book_title='Knowledge',
                chapter_title='Questions to the Prophet',
                score=0.84,
                matched_terms=('anger', 'do not get angry'),
                snippet='do not get angry',
                retrieval_method='python_fallback',
            )
        ],
    )
    assert result.abstain is True


def test_search_service_surfaces_llm_ready_evidence_bundle() -> None:
    service = HadithTopicalSearchService(candidate_generator=_StubCandidateGenerator([HadithTopicalCandidate(canonical_ref='hadith:sahih-al-bukhari-en:63', source_id='hadith:sahih-al-bukhari-en', retrieval_origin='lexical_fallback', matched_terms=('patience',), matched_topics=('patience',), central_topic_score=0.81, answerability_score=0.84, incidental_topic_penalty=0.05, guidance_role='virtue_statement', metadata={'contextual_summary': 'Patience is a gift.', 'english_text': 'Patience is a gift better and more comprehensive than anything else.'})]))
    result = service.search(
        raw_query='What did the Prophet say about patience?',
        collection_source_id='hadith:sahih-al-bukhari-en',
        lexical_hits=[
            HadithLexicalHit(
                entry=_entry('hadith:sahih-al-bukhari-en:63', 'Patience is a gift better and more comprehensive than anything else.'),
                display_name='Sahih al-Bukhari (English)',
                citation_label='Sahih al-Bukhari',
                book_title='Book of Patience',
                chapter_title='Patience',
                score=0.87,
                matched_terms=('patience',),
                snippet='Patience is a gift better and more comprehensive than anything else.',
                retrieval_method='python_fallback',
            )
        ],
    )

    assert result.abstain is False
    assert result.debug['evidence_bundle']['candidate_count'] >= 1
    assert result.debug['llm_composition_contract']['source_domain'] == 'hadith'


class _StubGuidanceRetriever:
    def __init__(self, candidates):
        self._candidates = candidates

    def retrieve(self, *, query, collection_source_id=None, limit=12):
        return list(self._candidates), {'stubbed_guidance': True, 'artifact_candidate_count': len(self._candidates)}


def test_search_service_prefers_guidance_unit_candidate_over_raw_row() -> None:
    guidance_candidate = HadithTopicalCandidate(
        canonical_ref='hadith:sahih-al-bukhari-en:63',
        source_id='hadith:sahih-al-bukhari-en',
        retrieval_origin='guidance_artifact',
        matched_terms=('anger',),
        matched_topics=('anger',),
        central_topic_score=0.91,
        answerability_score=0.88,
        incidental_topic_penalty=0.02,
        guidance_role='direct_moral_instruction',
        metadata={'guidance_unit_id': 'hu:bukhari:63:01', 'span_text': 'The Prophet said: Do not get angry.', 'contextual_summary': 'Direct guidance against anger.'},
    )
    raw_candidate = HadithTopicalCandidate(
        canonical_ref='hadith:sahih-al-bukhari-en:2620',
        source_id='hadith:sahih-al-bukhari-en',
        retrieval_origin='lexical_fallback',
        matched_terms=('anger',),
        central_topic_score=0.63,
        answerability_score=0.52,
        incidental_topic_penalty=0.64,
        guidance_role='narrative_incident',
    )
    service = HadithTopicalSearchService(
        candidate_generator=_StubCandidateGenerator([raw_candidate]),
        guidance_unit_retriever=_StubGuidanceRetriever([guidance_candidate]),
    )
    result = service.search(
        raw_query='What did the Prophet say about anger?',
        collection_source_id='hadith:sahih-al-bukhari-en',
        lexical_hits=[],
    )
    assert result.abstain is False
    assert result.selected[0].canonical_ref == 'hadith:sahih-al-bukhari-en:63'
    assert result.debug['selected_guidance_unit_ids'] == ['hu:bukhari:63:01']
