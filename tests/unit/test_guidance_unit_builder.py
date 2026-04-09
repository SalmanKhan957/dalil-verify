from domains.hadith.types import HadithEntryRecord
from pipelines.hadith_topical.build_guidance_units import build_guidance_units_for_entry


def _entry(text: str) -> HadithEntryRecord:
    return HadithEntryRecord(
        id=1,
        work_id=1,
        book_id=1,
        chapter_id=1,
        collection_source_id='hadith:sahih-al-bukhari-en',
        canonical_entry_id='entry:1',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:63',
        canonical_ref_book_hadith='hadith:sahih-al-bukhari-en:book:1:hadith:63',
        canonical_ref_book_chapter_hadith='hadith:sahih-al-bukhari-en:book:1:chapter:1:hadith:63',
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


def test_build_guidance_units_creates_direct_instruction_unit() -> None:
    units = build_guidance_units_for_entry(
        _entry('The Prophet said: Do not get angry. He repeated it several times. A believer restrains his anger.'),
    )
    assert units
    assert any(unit['guidance_role'] == 'direct_moral_instruction' for unit in units)
    assert any('anger' in unit['central_concept_ids'] or 'anger' in unit['secondary_concept_ids'] for unit in units)


def test_build_guidance_units_does_not_false_tag_lying_from_quality_words() -> None:
    units = build_guidance_units_for_entry(
        _entry('He spoke about qualities and good living during the journey, and the people discussed their provisions.'),
    )
    assert all('lying' not in unit['central_concept_ids'] for unit in units)
    assert all('lying' not in unit['secondary_concept_ids'] for unit in units)
