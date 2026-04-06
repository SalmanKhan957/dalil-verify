from __future__ import annotations

import pytest

from apps.ask_api.schemas import AskRequest


def test_request_schema_rejects_multiple_tafsir_source_ids() -> None:
    with pytest.raises(ValueError, match='at most one source id'):
        AskRequest(query='Explain 2:255', sources={'tafsir': {'source_ids': ['tafsir:ibn-kathir-en', 'tafsir:jalalayn-en']}})


def test_request_schema_rejects_multiple_hadith_collection_ids() -> None:
    with pytest.raises(ValueError, match='at most one source id'):
        AskRequest(query='Bukhari 2', sources={'hadith': {'collection_ids': ['hadith:sahih-al-bukhari-en', 'hadith:sahih-muslim-en']}})


def test_request_schema_rejects_tafsir_limit_when_mode_off() -> None:
    with pytest.raises(ValueError, match='sources.tafsir.limit cannot be supplied when sources.tafsir.mode=off'):
        AskRequest(query='Explain 2:255', sources={'tafsir': {'mode': 'off', 'limit': 2}})


def test_request_schema_rejects_conflicting_legacy_and_nested_aliases() -> None:
    with pytest.raises(ValueError, match='Conflicting request controls supplied'):
        AskRequest(
            query='Explain 2:255',
            include_tafsir=True,
            sources={'tafsir': {'mode': 'off'}},
        )


def test_request_schema_allows_matching_legacy_and_nested_aliases() -> None:
    request = AskRequest(
        query='Explain 2:255',
        include_tafsir=True,
        tafsir_source_id='tafsir:ibn-kathir-en',
        hadith_source_id='hadith:sahih-al-bukhari-en',
        diagnostics={'debug': True},
        debug=True,
        sources={
            'tafsir': {'mode': 'required', 'source_ids': ['tafsir:ibn-kathir-en']},
            'hadith': {'mode': 'explicit_lookup_only', 'collection_ids': ['hadith:sahih-al-bukhari-en']},
        },
    )

    assert request.effective_include_tafsir is True
    assert request.effective_tafsir_source_id == 'tafsir:ibn-kathir-en'
    assert request.effective_hadith_source_id == 'hadith:sahih-al-bukhari-en'
    assert request.source_controls_payload['hadith']['mode'] == 'explicit_lookup_only'
