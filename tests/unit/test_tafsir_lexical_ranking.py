from types import SimpleNamespace

from domains.tafsir.retrieval.scoring import score_tafsir_row


def test_tafsir_scoring_prefers_exact_hardship_ease_section() -> None:
    relevant = SimpleNamespace(
        surah_no=94,
        display_name='Tafsir Ibn Kathir',
        citation_label='Tafsir Ibn Kathir',
        quran_span_ref='94:5-6',
        anchor_verse_key='94:5',
        text_plain='Indeed with hardship comes ease. Relief follows difficulty.',
    )
    weaker = SimpleNamespace(
        surah_no=2,
        display_name='Tafsir Ibn Kathir',
        citation_label='Tafsir Ibn Kathir',
        quran_span_ref='2:45',
        anchor_verse_key='2:45',
        text_plain='Seek help through patience and prayer.',
    )

    relevant_score, relevant_terms = score_tafsir_row(relevant, 'ease after hardship', ['ease', 'hardship'])
    weaker_score, _ = score_tafsir_row(weaker, 'ease after hardship', ['ease', 'hardship'])

    assert relevant_score > weaker_score
    assert 'hardship' in relevant_terms
