from domains.hadith.ingestion.normalizer_meeatif import MeeAtifHadithCollectionNormalizer


def test_normalize_meeatif_bukhari_payload_models_book_layer_and_public_collection_numbers() -> None:
    payload = [
        {
            'Book': 'Sahih al-Bukhari',
            'Chapter_Number': 1,
            'Chapter_Title_Arabic': 'باب كَيْفَ كَانَ بَدْءُ الْوَحْىِ',
            'Chapter_Title_English': "Chapter: How the Divine Revelation started being revealed to Allah's Messenger",
            'Arabic_Text': 'حَدَّثَنَا ...',
            'English_Text': "Narrated 'Umar bin Al-Khattab: I heard Allah's Messenger say...",
            'Grade': '',
            'Reference': 'https://sunnah.com/bukhari:1',
            'In-book reference': 'Book 1, Hadith 1',
        },
        {
            'Book': 'Sahih al-Bukhari',
            'Chapter_Number': 2,
            'Chapter_Title_Arabic': 'باب ...',
            'Chapter_Title_English': 'Chapter: Faith has over sixty branches',
            'Arabic_Text': 'حَدَّثَنَا ... ٢',
            'English_Text': 'Narrated Abu Huraira: Faith has over sixty branches...',
            'Grade': '',
            'Reference': 'https://sunnah.com/bukhari:9',
            'In-book reference': 'Book 2, Hadith 1',
        },
    ]

    batch = MeeAtifHadithCollectionNormalizer().normalize(payload)

    assert batch.collection_seed.source_id == 'hadith:sahih-al-bukhari-en'
    assert len(batch.books) == 2
    assert batch.books[0].book_number == 1
    assert batch.books[0].title_en == "Chapter: How the Divine Revelation started being revealed to Allah's Messenger"
    assert len(batch.chapters) == 0
    assert len(batch.entries) == 2
    assert batch.entries[0].canonical_ref_collection == 'hadith:sahih-al-bukhari-en:1'
    assert batch.entries[0].canonical_ref_book_hadith == 'hadith:sahih-al-bukhari-en:book:1:hadith:1'
    assert batch.entries[0].canonical_ref_book_chapter_hadith is None
    assert batch.entries[0].chapter_number is None
    assert batch.entries[0].canonical_chapter_id is None
    assert batch.entries[0].english_narrator == "Narrated 'Umar bin Al-Khattab:"
    assert batch.entries[0].english_text == "I heard Allah's Messenger say..."
    assert batch.entries[0].metadata_json['reference_url'] == 'https://sunnah.com/bukhari:1'
    assert batch.entries[0].metadata_json['public_collection_number'] == 1
    assert batch.entries[0].metadata_json['in_book_book_number'] == 1
    assert batch.entries[0].metadata_json['in_book_hadith_number'] == 1
    assert batch.entries[1].book_number == 2
    assert batch.entries[1].collection_hadith_number == 9
    assert batch.manifest.numbering_scheme == 'collection_number_reference_url_linked'
