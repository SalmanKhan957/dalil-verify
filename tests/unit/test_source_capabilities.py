from domains.source_registry.capabilities import list_enabled_capabilities, source_supports_capability
from domains.source_registry.registry import get_source_record


def test_bootstrap_registry_exposes_capability_matrix() -> None:
    quran = get_source_record('quran:tanzil-simple')
    tafsir = get_source_record('tafsir:ibn-kathir-en')
    hadith = get_source_record('hadith:sahih-al-bukhari-en')

    assert quran is not None and tafsir is not None and hadith is not None
    assert source_supports_capability(quran, 'quote_verification') is True
    assert source_supports_capability(tafsir, 'composition_allowed') is True
    assert source_supports_capability(tafsir, 'topical_retrieval') is True
    assert source_supports_capability(hadith, 'explicit_lookup') is True
    assert source_supports_capability(hadith, 'topical_retrieval') is True
    assert 'conversation_followup_anchor' in list_enabled_capabilities(hadith)
