from services.ask_workflows.dispatch import dispatch_ask_query



def test_dispatch_routes_tafsir_intent_to_answer_flow(monkeypatch) -> None:
    import services.ask_workflows.dispatch as dispatch_module

    monkeypatch.setattr(
        dispatch_module,
        "explain_answer",
        lambda **kwargs: {
            "ok": True,
            "query": kwargs["query"],
            "answer_mode": "explain",
            "route_type": "explicit_quran_reference",
            "action_type": "explain",
            "answer_text": "Composed answer.",
            "citations": [],
            "quran_support": None,
            "tafsir_support": [],
            "resolution": {"canonical_source_id": "quran:112:1-4"},
            "debug": None,
            "error": None,
        },
    )

    result = dispatch_ask_query("Tafsir of Surah Ikhlas")

    assert result["ok"] is True
    assert result["result"]["answer_text"] == "Composed answer."
