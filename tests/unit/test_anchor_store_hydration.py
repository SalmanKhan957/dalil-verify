from domains.conversation.anchor_store import hydrate_request_context, save_response_anchors


def test_hydrate_request_context_uses_parent_turn_record() -> None:
    record = save_response_anchors(
        session_key="conversation:test",
        anchors=[{"canonical_ref": "quran:2:255", "source_domain": "quran"}],
    )
    assert record is not None

    hydrated = hydrate_request_context(
        request_context={"parent_turn_id": record.turn_id},
        session_key="conversation:test",
        followup_like=True,
    )

    assert hydrated["anchor_refs"] == ["quran:2:255"]
    assert hydrated["_anchor_resolution_mode"] == "parent_turn_hydrated"
    assert hydrated["_anchor_session_key"] == "conversation:test"


def test_hydrate_request_context_uses_latest_session_record_for_followup() -> None:
    record = save_response_anchors(
        session_key="implicit:test",
        anchors=[{"canonical_ref": "hadith:sahih-al-bukhari-en:7", "source_domain": "hadith"}],
    )
    assert record is not None

    hydrated = hydrate_request_context(
        request_context={},
        session_key="implicit:test",
        followup_like=True,
    )

    assert hydrated["anchor_refs"] == ["hadith:sahih-al-bukhari-en:7"]
    assert hydrated["_anchor_resolution_mode"] == "implicit_session_hydrated"
    assert hydrated["_anchor_session_key"] == "implicit:test"
