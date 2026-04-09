from __future__ import annotations

from unittest.mock import patch

from domains.answer_engine.domain_invocation import invoke_hadith_domain
from domains.ask.planner_types import AskPlan, DomainInvocation, EvidenceDomain, ResponseMode
from domains.hadith.contracts import HadithLexicalHit
from domains.hadith.types import HadithEntryRecord
from domains.hadith_topical.contracts import HadithTopicalResult


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
        collection_hadith_number=3464,
        in_book_hadith_number=3464,
        book_number=1,
        chapter_number=1,
        english_narrator='Narrated Ibn `Abbas:',
        english_text=text,
        arabic_text=None,
        narrator_chain_text=None,
        matn_text=None,
        metadata_json={},
        raw_json={},
        grading=None,
    )


def _plan(query: str) -> AskPlan:
    return AskPlan(
        query=query,
        route_type='topical_hadith_query',
        action_type='explain',
        response_mode=ResponseMode.TOPICAL_HADITH,
        eligible_domains=[EvidenceDomain.HADITH],
        selected_domains=[EvidenceDomain.HADITH],
        hadith_plan=DomainInvocation(
            domain=EvidenceDomain.HADITH,
            source_id='hadith:sahih-al-bukhari-en',
            params={
                'retrieval_mode': 'topical_v2_shadow',
                'query_text': query,
                'source_id': 'hadith:sahih-al-bukhari-en',
                'limit': 5,
                'minimum_score': 0.0,
            },
        ),
    )


def test_domain_invocation_blocks_legacy_fallback_for_entity_family() -> None:
    baseline_hits = [
        HadithLexicalHit(
            entry=_entry('hadith:sahih-al-bukhari-en:3464', 'The Prophet visited a sick bedouin and said no harm will befall you.'),
            display_name='Sahih al-Bukhari (English)',
            citation_label='Sahih al-Bukhari',
            book_title='Patients',
            chapter_title='Visiting the sick',
            score=0.91,
            matched_terms=('prophet', 'said'),
            snippet='The Prophet visited a sick bedouin and said no harm will befall you.',
            retrieval_method='python_fallback',
        )
    ]
    shadow_result = HadithTopicalResult(
        selected=(),
        abstain=True,
        abstain_reason='insufficient_ranked_evidence',
        warnings=('no_family_aligned_thematic_passages',),
        debug={
            'retrieval_family': 'entity_eschatology',
            'family_decision': {'allow_generic_fallback': False},
        },
    )
    with patch('domains.hadith.service.HadithService.search_topically', return_value=baseline_hits), patch('domains.hadith_topical.search_service.HadithTopicalSearchService.search', return_value=shadow_result):
        evidence = invoke_hadith_domain(_plan('What did the Prophet ﷺ say about the Mahdi?'))
    assert evidence.hadith is None
    assert 'insufficient_evidence' in evidence.errors
    assert 'no_family_safe_topical_match' in evidence.warnings


def test_domain_invocation_keeps_lexical_fallback_for_moral_guidance() -> None:
    baseline_hits = [
        HadithLexicalHit(
            entry=_entry('hadith:sahih-al-bukhari-en:5830', 'The Prophet became changed with anger and said Musa remained patient.'),
            display_name='Sahih al-Bukhari (English)',
            citation_label='Sahih al-Bukhari',
            book_title='Manners',
            chapter_title='Anger',
            score=0.91,
            matched_terms=('anger',),
            snippet='The Prophet became changed with anger and said Musa remained patient.',
            retrieval_method='python_fallback',
        )
    ]
    shadow_result = HadithTopicalResult(
        selected=(),
        abstain=True,
        abstain_reason='insufficient_ranked_evidence',
        warnings=('no_ranked_candidate_passed_thresholds',),
        debug={
            'retrieval_family': 'moral_guidance',
            'family_decision': {'allow_generic_fallback': True},
        },
    )
    with patch('domains.hadith.service.HadithService.search_topically', return_value=baseline_hits), patch('domains.hadith_topical.search_service.HadithTopicalSearchService.search', return_value=shadow_result):
        evidence = invoke_hadith_domain(_plan('What did the Prophet ﷺ say about anger?'))
    assert evidence.hadith is not None
    assert evidence.hadith.canonical_ref == 'hadith:sahih-al-bukhari-en:5830'
