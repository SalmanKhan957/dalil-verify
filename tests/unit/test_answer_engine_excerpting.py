from domains.answer_engine.excerpting import build_tafsir_excerpt



def test_build_tafsir_excerpt_returns_full_text_when_short() -> None:
    text = "Allah is One and Unique."
    excerpt, trimmed = build_tafsir_excerpt(text)

    assert excerpt == text
    assert trimmed is False



def test_build_tafsir_excerpt_trims_long_text_cleanly() -> None:
    text = ("Sentence one. " * 80).strip()
    excerpt, trimmed = build_tafsir_excerpt(text, target_chars=500)

    assert trimmed is True
    assert len(excerpt) <= 520
    assert excerpt.endswith(".")
