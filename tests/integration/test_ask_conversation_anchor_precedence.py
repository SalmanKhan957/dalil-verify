from domains.conversation.anchor_store import hydrate_request_context


def test_latest_relevant_anchor_precedence_preserves_request_supplied_anchor_refs() -> None:
    context = hydrate_request_context(
        request_context={'anchor_refs': ['quran:2:255'], 'conversation_id': 'conv-precedence'},
        session_key='conversation:conv-precedence',
        followup_like=True,
    )
    assert context['anchor_refs'] == ['quran:2:255']
    assert context['_anchor_resolution_mode'] == 'request_supplied'
