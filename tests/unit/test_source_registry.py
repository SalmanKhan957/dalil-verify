from domains.source_registry.policies import can_mix_sources, can_use_source_for_answering
from domains.source_registry.registry import (
    get_default_quran_text_source,
    get_default_quran_translation_source,
    get_source_record,
    get_source_records_by_domain,
    is_source_enabled,
    resolve_quran_text_source,
    resolve_quran_translation_source,
)


def test_quran_sources_are_present_and_enabled():
    quran_sources = get_source_records_by_domain("quran")

    assert len(quran_sources) >= 2
    assert is_source_enabled("quran:tanzil-simple") is True
    assert is_source_enabled("quran:towards-understanding-en") is True



def test_tafsir_is_now_enabled_while_hadith_remains_placeholder():
    tafsir_source = get_source_record("tafsir:ibn-kathir-en")
    hadith_source = get_source_record("hadith:sahih-bukhari-en")

    assert tafsir_source is not None
    assert hadith_source is not None
    assert can_use_source_for_answering(tafsir_source) is True
    assert can_use_source_for_answering(hadith_source) is False



def test_source_policy_allows_quran_tafsir_bounded_composition():
    quran_text = get_source_record("quran:tanzil-simple")
    quran_translation = get_source_record("quran:towards-understanding-en")
    tafsir_source = get_source_record("tafsir:ibn-kathir-en")

    assert quran_text is not None
    assert quran_translation is not None
    assert tafsir_source is not None

    assert can_mix_sources(quran_text, quran_translation) is True
    assert can_mix_sources(quran_text, tafsir_source) is True



def test_default_quran_sources_resolve_from_registry() -> None:
    text_source = get_default_quran_text_source()
    translation_source = get_default_quran_translation_source()

    assert text_source is not None
    assert text_source.source_id == "quran:tanzil-simple"
    assert translation_source is not None
    assert translation_source.source_id == "quran:towards-understanding-en"



def test_quran_source_resolution_validates_kind_and_enabled_status() -> None:
    assert resolve_quran_text_source("quran:tanzil-simple").source_id == "quran:tanzil-simple"
    assert resolve_quran_translation_source("quran:towards-understanding-en").source_id == "quran:towards-understanding-en"
    assert resolve_quran_text_source("quran:towards-understanding-en") is None
    assert resolve_quran_translation_source("hadith:sahih-bukhari-en") is None
