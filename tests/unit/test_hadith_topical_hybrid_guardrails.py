from __future__ import annotations

from domains.hadith.contracts import HadithLexicalHit
from domains.hadith.types import HadithEntryRecord
from domains.hadith_topical.query_family_classifier import classify_hadith_topic_family
from domains.hadith_topical.query_normalizer import normalize_hadith_topical_query
from domains.hadith_topical.thematic_passage_retriever import HadithThematicPassageRetriever


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


def test_thematic_retriever_prefers_hour_alias_hit_over_generic_overlap() -> None:
    query = normalize_hadith_topical_query('What did the Prophet ﷺ say about the signs of the Hour?')
    decision = classify_hadith_topic_family(query)
    retriever = HadithThematicPassageRetriever()
    hits = [
        HadithLexicalHit(
            entry=_entry('hadith:sahih-al-bukhari-en:1', 'A long narrative about Aisha and jealousy.'),
            display_name='Sahih al-Bukhari (English)',
            citation_label='Sahih al-Bukhari',
            book_title='Stories',
            chapter_title='Narrative',
            score=0.95,
            matched_terms=('prophet', 'said'),
            snippet='A long narrative about Aisha and jealousy.',
            retrieval_method='python_fallback',
        ),
        HadithLexicalHit(
            entry=_entry('hadith:sahih-al-bukhari-en:2', 'The Prophet mentioned some of the signs before the Hour is established.'),
            display_name='Sahih al-Bukhari (English)',
            citation_label='Sahih al-Bukhari',
            book_title='Trials',
            chapter_title='Signs of the Hour',
            score=0.62,
            matched_terms=('hour',),
            snippet='The Prophet mentioned some of the signs before the Hour is established.',
            retrieval_method='python_fallback',
        ),
    ]
    candidates, debug = retriever.retrieve(query=query, family_decision=decision, lexical_hits=hits, collection_source_id='hadith:sahih-al-bukhari-en', limit=5)
    assert len(candidates) == 1
    assert candidates[0].canonical_ref == 'hadith:sahih-al-bukhari-en:2'
    assert debug['candidate_count'] == 1
