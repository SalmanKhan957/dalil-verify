from types import SimpleNamespace

from domains.hadith.retrieval.scoring import score_hadith_row


def test_hadith_scoring_prefers_revelation_title_even_with_typo() -> None:
    revelation = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Revelation',
        chapter_title='How the Divine Inspiration started',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:1',
        english_narrator='Narrated Umar bin Al-Khattab:',
        english_text='Actions are judged by intentions.',
        matn_text='Every person will get the reward according to what he intended.',
    )
    faith = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Faith',
        chapter_title='Faith has many branches',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:2',
        english_narrator='Narrated Abu Huraira:',
        english_text='Faith has over sixty branches.',
        matn_text=None,
    )

    revelation_score, revelation_terms = score_hadith_row(revelation, 'revalation', ['revalation'])
    faith_score, _ = score_hadith_row(faith, 'revalation', ['revalation'])

    assert revelation_score > faith_score
    assert revelation_terms



def test_hadith_scoring_does_not_treat_impatience_as_patience_match() -> None:
    patience = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Funerals',
        chapter_title='Patience at the first stroke of calamity',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:1260',
        english_narrator='Narrated Anas:',
        english_text='The real patience is at the first stroke of a calamity.',
        matn_text=None,
    )
    impatience = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Invocations',
        chapter_title='Supplication',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:6103',
        english_narrator='Narrated Abu Huraira:',
        english_text='The invocation is granted if he does not show impatience.',
        matn_text=None,
    )

    patience_score, patience_terms = score_hadith_row(patience, 'patience', ['patience'])
    impatience_score, impatience_terms = score_hadith_row(impatience, 'patience', ['patience'])

    assert patience_score > impatience_score
    assert 'patience' in patience_terms
    assert 'patience' not in impatience_terms



def test_hadith_scoring_prefers_direct_concise_patience_hadith_over_broad_narrative() -> None:
    direct = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Funerals',
        chapter_title='Patience',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:1260',
        english_narrator='Narrated Anas:',
        english_text='The real patience is at the first stroke of a calamity.',
        matn_text=None,
    )
    broad = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Friday Prayer',
        chapter_title='Friday Prayer',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:901',
        english_narrator='Narrated `Amr bin Taghlib:',
        english_text="Some property was brought to Allah's Messenger and he distributed it. He said that he gives to some people because they have no patience and leaves those who are patient and self-content with the goodness Allah has put into their hearts.",
        matn_text=None,
    )

    direct_score, _ = score_hadith_row(direct, 'patience', ['patience'])
    broad_score, _ = score_hadith_row(broad, 'patience', ['patience'])

    assert direct_score > broad_score



def test_hadith_scoring_prefers_do_not_get_angry_guidance_over_incidental_anger_mention() -> None:
    guidance = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Knowledge',
        chapter_title='Questions and answers',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:63',
        english_narrator='Narrated Anas:',
        english_text='The man said: do not get angry. The Prophet said: Ask whatever you want.',
        matn_text=None,
    )
    incidental = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Clothing',
        chapter_title='Silk',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:5152',
        english_narrator='Narrated Ali:',
        english_text='I noticed anger on his face after I wore the silk suit and then distributed it among my women-folk.',
        matn_text=None,
    )

    guidance_score, guidance_terms = score_hadith_row(guidance, 'anger', ['anger'])
    incidental_score, _ = score_hadith_row(incidental, 'anger', ['anger'])

    assert guidance_score > incidental_score
    assert guidance_terms


def test_hadith_scoring_maps_rizq_to_sustenance_language() -> None:
    sustenance = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Good Manners',
        chapter_title='Keeping ties',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:1992',
        english_narrator='Narrated Anas:',
        english_text='Whoever desires an expansion in his sustenance and age should keep good relations with his kin.',
        matn_text=None,
    )
    unrelated = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Pilgrimage',
        chapter_title='Water distribution',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:1683',
        english_narrator='Narrated Ibn Umar:',
        english_text='The Prophet allowed Al-Abbas to stay in Mecca during Mina in order to provide water to the people.',
        matn_text=None,
    )

    sustenance_score, sustenance_terms = score_hadith_row(sustenance, 'rizq', ['rizq'])
    unrelated_score, _ = score_hadith_row(unrelated, 'rizq', ['rizq'])

    assert sustenance_score > unrelated_score
    assert 'rizq' in sustenance_terms


def test_hadith_scoring_penalizes_incidental_anger_face_mention() -> None:
    incidental = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Clothing',
        chapter_title='Silk',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:5152',
        english_narrator='Narrated Ali:',
        english_text='I noticed anger on his face after I wore the silk suit and then distributed it among my women-folk.',
        matn_text=None,
    )
    generic = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Misc',
        chapter_title='Misc',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:9000',
        english_narrator='Narrated Someone:',
        english_text='The people were angry and upset during the dispute.',
        matn_text=None,
    )

    incidental_score, _ = score_hadith_row(incidental, 'anger', ['anger'])
    generic_score, _ = score_hadith_row(generic, 'anger', ['anger'])

    assert incidental_score < generic_score


def test_hadith_scoring_boosts_rizq_relation_guidance() -> None:
    guidance = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Good Manners',
        chapter_title='Keeping ties',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:1992',
        english_narrator='Narrated Anas:',
        english_text='Whoever desires an expansion in his sustenance and age should keep good relations with his kith and kin.',
        matn_text=None,
    )
    weak = SimpleNamespace(
        display_name='Sahih al-Bukhari',
        citation_label='Sahih al-Bukhari',
        book_title='Misc',
        chapter_title='Misc',
        canonical_ref_collection='hadith:sahih-al-bukhari-en:3000',
        english_narrator='Narrated Someone:',
        english_text='The Prophet provided them with mounts after the war booty arrived.',
        matn_text=None,
    )

    guidance_score, guidance_terms = score_hadith_row(guidance, 'rizq', ['rizq'])
    weak_score, _ = score_hadith_row(weak, 'rizq', ['rizq'])

    assert guidance_score > weak_score
    assert 'rizq' in guidance_terms
