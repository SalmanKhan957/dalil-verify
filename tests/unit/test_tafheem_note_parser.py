from domains.tafsir.tafheem_notes import build_tafheem_render_payload, parse_tafheem_raw_text


def test_parse_tafheem_raw_text_extracts_note_entries_and_commentary_rendering() -> None:
    raw_text = (
        'Allah, the Ever-Living[[This affirms exclusive divine sovereignty.]] '
        'Neither slumber seizes Him[[This refutes anthropomorphic weakness.]]'
    )

    parsed = parse_tafheem_raw_text(raw_text)

    assert parsed.display_text == 'Allah, the Ever-Living Neither slumber seizes Him'
    assert parsed.inline_note_count == 2
    assert parsed.note_entries[0].anchor_text == 'Allah, the Ever-Living'
    assert parsed.note_entries[0].note_text == 'This affirms exclusive divine sovereignty.'
    assert 'On "Allah, the Ever-Living": This affirms exclusive divine sovereignty.' in parsed.commentary_text_plain
    assert '<h2>Commentary</h2>' in parsed.commentary_text_html


def test_build_tafheem_render_payload_reconstructs_commentary_from_existing_raw_json() -> None:
    payload = build_tafheem_render_payload(
        raw_json={
            'raw_text': 'Say[[The command is addressed first to the Prophet.]] He is Allah[[This identifies the true Lord.]]',
            'inline_note_count': 2,
        },
        fallback_text_plain='Say He is Allah',
        fallback_text_html='Say He is Allah',
    )

    assert payload['rendering_mode'] == 'tafheem_commentary_reconstructed'
    assert payload['inline_note_count'] == 2
    assert 'The command is addressed first to the Prophet.' in payload['excerpt_source_text']
    assert '<strong>On' in payload['text_html']
