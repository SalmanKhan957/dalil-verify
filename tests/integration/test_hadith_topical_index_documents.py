from pipelines.indexing.hadith.build_hadith_topical_documents import build_document_from_record


def test_index_document_contains_enrichment_fields() -> None:
    record = {
        'canonical_ref': 'hadith:sahih-al-bukhari-en:63',
        'collection_source_id': 'hadith:sahih-al-bukhari-en',
        'collection_slug': 'sahih-al-bukhari-en',
        'collection_hadith_number': 63,
        'book_number': 1,
        'chapter_number': 3,
        'numbering_quality': 'reference_url_linked',
        'english_text': 'The man said, do not get angry, and the Prophet said ask whatever you want.',
        'chapter_title_en': 'Chapter: Questions to the Prophet about anger',
        'book_title_en': 'Book 1',
        'reference_url': 'https://sunnah.com/bukhari:63',
        'in_book_reference_text': 'Book 1, Hadith 63',
    }
    document = build_document_from_record(record)
    assert document['canonical_ref'] == 'hadith:sahih-al-bukhari-en:63'
    assert document['baab_plus_matn_en'].startswith('Chapter: Questions to the Prophet about anger')
    assert document['reference_url'] == 'https://sunnah.com/bukhari:63'
    assert document['in_book_reference_text'] == 'Book 1, Hadith 63'
    assert 'anger' in document['topic_tags']
    assert 'prohibition' in document['directive_labels']
    assert 'qa_exchange' in document['directive_labels']
    assert 'question_answer_exchange' in document['subtopic_tags']
    assert document['topic_family'] == 'akhlaq'
    assert document['guidance_role']
    assert isinstance(document['answerability_score'], float)
    assert isinstance(document['central_topic_score'], float)
