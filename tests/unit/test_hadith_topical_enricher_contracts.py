from domains.hadith_topical.enricher import build_enriched_document


def test_enricher_assigns_rizq_tags_and_context_flags() -> None:
    document = build_enriched_document(
        canonical_ref='hadith:sahih-al-bukhari-en:1471',
        collection_source_id='hadith:sahih-al-bukhari-en',
        collection_slug='sahih-al-bukhari-en',
        collection_hadith_number=1471,
        book_number=1,
        chapter_number=25,
        numbering_quality='collection_number_stable',
        english_text='The people of Yemen came for Hajj without provisions and Allah revealed take provision for the journey.',
        chapter_title_en='Provisions for Hajj',
        book_title_en='Hajj',
    )
    assert 'rizq' in document.topic_tags
    assert 'travel_provision' in document.subtopic_tags
    assert document.central_topic_score > 0.5
    assert document.topic_family == 'wealth'


def test_enricher_marks_incidental_anger_risk_for_long_narrative_without_core_phrase() -> None:
    document = build_enriched_document(
        canonical_ref='hadith:sahih-al-bukhari-en:5152',
        collection_source_id='hadith:sahih-al-bukhari-en',
        collection_slug='sahih-al-bukhari-en',
        collection_hadith_number=5152,
        book_number=1,
        chapter_number=69,
        numbering_quality='collection_number_stable',
        english_text=(
            'The Prophet gave me a silk suit and I wore it, but when I noticed anger on his face, '
            'I cut it and distributed it among my women-folk. This was part of a longer narrative '
            'that is not primarily a teaching chapter about anger control or anger warnings.'
        ),
        chapter_title_en='Clothing',
        book_title_en='Dress',
    )
    assert 'anger' in document.topic_tags
    assert 'incidental_mention_risk' in document.incidental_topic_flags
    assert document.answerability_score < document.central_topic_score


def test_enricher_marks_context_specific_jealousy_as_narrative_incident() -> None:
    document = build_enriched_document(
        canonical_ref='hadith:sahih-al-bukhari-en:4708',
        collection_source_id='hadith:sahih-al-bukhari-en',
        collection_slug='sahih-al-bukhari-en',
        collection_hadith_number=4708,
        book_number=1,
        chapter_number=65,
        numbering_quality='collection_number_stable',
        english_text='The wives of the Prophet out of their jealousy backed each other against the Prophet and a verse was revealed.',
        chapter_title_en='Tafsir of a verse',
        book_title_en='Tafsir',
    )
    assert 'hasad' in document.topic_tags
    assert document.guidance_role == 'narrative_incident'
    assert 'jealousy_context_specific' in document.incidental_topic_flags
