from __future__ import annotations

from domains.hadith.contracts import HadithLexicalHit
from domains.hadith.types import HadithEntryRecord
from domains.hadith_topical.search_service import HadithTopicalSearchService


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


def test_search_service_uses_thematic_family_and_blocks_generic_fallback() -> None:
    service = HadithTopicalSearchService()
    result = service.search(
        raw_query='What did the Prophet ﷺ say about coming of Dajjal?',
        collection_source_id='hadith:sahih-al-bukhari-en',
        lexical_hits=[
            HadithLexicalHit(
                entry=_entry('hadith:sahih-al-bukhari-en:3464', 'The Prophet visited a sick bedouin and said no harm will befall you.'),
                display_name='Sahih al-Bukhari (English)',
                citation_label='Sahih al-Bukhari',
                book_title='Patients',
                chapter_title='Visiting the sick',
                score=0.95,
                matched_terms=('prophet', 'said'),
                snippet='The Prophet visited a sick bedouin and said no harm will befall you.',
                retrieval_method='python_fallback',
            )
        ],
    )
    assert result.abstain is True
    assert result.debug['retrieval_family'] == 'entity_eschatology'
    assert result.debug['thematic_passage_retrieval']['candidate_count'] == 0


def test_search_service_selects_family_aligned_thematic_passage() -> None:
    service = HadithTopicalSearchService()
    result = service.search(
        raw_query='What did the Prophet ﷺ say about coming of Dajjal?',
        collection_source_id='hadith:sahih-al-bukhari-en',
        lexical_hits=[
            HadithLexicalHit(
                entry=_entry('hadith:sahih-al-bukhari-en:9999', 'The Prophet warned about Al-Masih ad-Dajjal and his trial.'),
                display_name='Sahih al-Bukhari (English)',
                citation_label='Sahih al-Bukhari',
                book_title='Trials',
                chapter_title='Mention of Dajjal',
                score=0.77,
                matched_terms=('dajjal',),
                snippet='The Prophet warned about Al-Masih ad-Dajjal and his trial.',
                retrieval_method='python_fallback',
            )
        ],
    )
    assert result.abstain is False
    assert result.selected[0].canonical_ref == 'hadith:sahih-al-bukhari-en:9999'
    assert result.debug['retrieval_family'] == 'entity_eschatology'
    assert result.debug['selected_thematic_passages'] == ['hadith:sahih-al-bukhari-en:9999']
