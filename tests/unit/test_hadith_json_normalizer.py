from domains.hadith.ingestion.normalizer import HadithCollectionNormalizer


def test_normalize_hadith_json_book_payload() -> None:
    payload = {
        'id': 1,
        'metadata': {
            'length': 2,
            'arabic': {'title': 'صحيح البخاري', 'author': 'الإمام البخاري'},
            'english': {'title': 'Sahih al-Bukhari', 'author': 'Imam al-Bukhari'},
        },
        'chapters': [
            {'id': 11, 'bookId': 1, 'arabic': 'بدء الوحي', 'english': 'Revelation'},
            {'id': 12, 'bookId': 1, 'arabic': 'الإيمان', 'english': 'Faith'},
        ],
        'hadiths': [
            {
                'id': 1,
                'idInBook': 1,
                'arabic': 'حَدَّثَنَا ...',
                'english': {'narrator': 'Narrated Umar bin Al-Khattab:', 'text': "I heard Allah's Messenger say..."},
                'chapterId': 11,
                'bookId': 1,
            },
            {
                'id': 2,
                'idInBook': 1,
                'arabic': 'حَدَّثَنَا ... ٢',
                'english': {'narrator': 'Narrated Abu Huraira:', 'text': 'Faith has over sixty branches...'},
                'chapterId': 12,
                'bookId': 1,
            },
        ],
    }

    batch = HadithCollectionNormalizer().normalize(payload)

    assert batch.collection_seed.source_id == 'hadith:sahih-al-bukhari-en'
    assert batch.collection_seed.enabled is True
    assert batch.collection_seed.approved_for_answering is False
    assert len(batch.books) == 1
    assert batch.books[0].canonical_book_id == 'hadith:sahih-al-bukhari-en:book:1'
    assert len(batch.chapters) == 2
    assert batch.chapters[0].canonical_chapter_id == 'hadith:sahih-al-bukhari-en:book:1:chapter:1'
    assert len(batch.entries) == 2
    assert batch.entries[0].canonical_ref_collection == 'hadith:sahih-al-bukhari-en:1'
    assert batch.entries[0].canonical_ref_book_hadith == 'hadith:sahih-al-bukhari-en:book:1:hadith:1'
    assert batch.entries[1].canonical_ref_book_chapter_hadith == 'hadith:sahih-al-bukhari-en:book:1:chapter:2:hadith:1'
    assert batch.manifest.expected_entries == 2
