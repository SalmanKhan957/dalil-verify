from __future__ import annotations

import httpx
import pytest

from apps.ask_api.main import app


ANSWER_SURFACE_FIELDS = (
    "answer_mode",
    "answer_text",
    "citations",
    "quran_support",
    "tafsir_support",
    "resolution",
    "partial_success",
    "warnings",
    "quran_source_selection",
)


@pytest.mark.anyio
async def test_ask_and_explain_surfaces_align_for_answer_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    import domains.ask.dispatcher as dispatcher_module

    shared_result = {
        "ok": True,
        "query": "112:1-2",
        "answer_mode": "quran_text",
        "route_type": "explicit_quran_reference",
        "action_type": "explain",
        "answer_text": "Quran 112:1-2 says: Say: He is Allah, the One.",
        "citations": [
            {
                "source_id": "quran:tanzil-simple",
                "citation_text": "Quran 112:1-2",
                "canonical_ref": "quran:112:1-2",
                "source_domain": "quran",
            }
        ],
        "quran_support": {
            "citation_string": "Quran 112:1-2",
            "surah_no": 112,
            "ayah_start": 1,
            "ayah_end": 2,
            "surah_name_en": "Al-Ikhlas",
            "surah_name_ar": "الإخلاص",
            "arabic_text": "قُلْ هُوَ اللَّهُ أَحَدٌ",
            "translation_text": "Say: He is Allah, the One.",
            "canonical_source_id": "quran:112:1-2",
            "translation_source_id": "quran:towards-understanding-en",
            "quran_source_id": "quran:tanzil-simple",
        },
        "tafsir_support": [],
        "resolution": {"canonical_source_id": "quran:112:1-2"},
        "partial_success": False,
        "warnings": [],
        "quran_source_selection": {
            "repository_mode": "csv",
            "source_resolution_strategy": "registry",
            "requested_quran_text_source_id": None,
            "requested_quran_translation_source_id": None,
            "selected_quran_text_source_id": "quran:tanzil-simple",
            "selected_quran_translation_source_id": "quran:towards-understanding-en",
        },
        "debug": None,
        "error": None,
    }

    monkeypatch.setattr(
        dispatcher_module,
        "classify_ask_query",
        lambda query: {"route_type": "explicit_quran_reference", "action_type": "explain"},
    )
    monkeypatch.setattr(dispatcher_module, "explain_answer", lambda **kwargs: shared_result)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            ask_response = await client.post("/ask", json={"query": "112:1-2"})
            explain_response = await client.post(
                "/ask/explain",
                json={"query": "112:1-2", "include_tafsir": False},
            )

    assert ask_response.status_code == 200
    assert explain_response.status_code == 200

    ask_body = ask_response.json()
    explain_body = explain_response.json()

    for field in ANSWER_SURFACE_FIELDS:
        assert ask_body[field] == explain_body[field]

    assert ask_body["result"]["answer_text"] == explain_body["answer_text"]
    assert ask_body["route_type"] == "explicit_quran_reference"
    assert ask_body["action_type"] == "explain"
