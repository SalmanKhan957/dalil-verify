from domains.ask.heuristics import detect_action_type


def test_detect_action_type_prefers_fetch_for_what_does_reference_say_queries() -> None:
    result = detect_action_type('What does 94:5-6 say?', route_hint='explicit_quran_reference')
    assert result['action_type'] == 'fetch_text'
