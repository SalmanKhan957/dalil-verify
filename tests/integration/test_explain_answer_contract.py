from __future__ import annotations

import httpx
import pytest

from apps.ask_api.main import app


@pytest.mark.anyio
async def test_explain_route_returns_answer_first_contract(monkeypatch) -> None:
    import apps.ask_api.routes.explain as explain_route_module

    monkeypatch.setattr(
        explain_route_module,
        "explain_answer",
        lambda **kwargs: {
            "ok": True,
            "query": kwargs["query"],
            "answer_mode": "explain",
            "route_type": "explicit_quran_reference",
            "action_type": "explain",
            "answer_text": "Quran 112:1-4 says: Say: He is Allah, the One.",
            "citations": [
                {
                    "source_id": "quran:tanzil-simple",
                    "citation_text": "Quran 112:1-4",
                    "canonical_ref": "quran:112:1-4",
                    "source_domain": "quran",
                }
            ],
            "quran_support": {
                "citation_string": "Quran 112:1-4",
                "surah_no": 112,
                "ayah_start": 1,
                "ayah_end": 4,
                "surah_name_en": "Al-Ikhlas",
                "surah_name_ar": "الإخلاص",
                "arabic_text": "قُلْ هُوَ اللَّهُ أَحَدٌ",
                "translation_text": "Say: He is Allah, the One.",
                "canonical_source_id": "quran:112:1-4",
                "translation_source_id": "quran:towards-understanding-en",
            },
            "tafsir_support": [],
            "resolution": {"canonical_source_id": "quran:112:1-4"},
            "debug": None,
            "error": None,
        },
    )

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask/explain",
                json={"query": "What does 112:1-4 say?", "include_tafsir": False},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["answer_text"].startswith("Quran 112:1-4")
    assert "quran_support" in body
    assert "tafsir_support" in body
    assert "citations" in body
