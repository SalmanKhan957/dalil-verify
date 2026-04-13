import pytest

pytest.importorskip('sqlalchemy')

from domains.ask.planner import build_ask_plan


def test_out_of_scope_followup_abstains_cleanly() -> None:
    state_payload = {
        'scope': {
            'domains': ['quran', 'tafsir'],
            'quran_ref': 'quran:112:1-4',
            'quran_span_ref': 'quran:112:1-4',
            'tafsir_source_ids': ['tafsir:tafheem-al-quran-en'],
        },
        'anchors': {'refs': ['quran:112:1-4'], 'domains': ['quran', 'tafsir']},
        'followup_ready': True,
    }
    plan = build_ask_plan('Summarize this hadith', request_context={'_hydrated_session_state': state_payload})
    assert plan.should_abstain is True
    assert plan.followup_rejected is True
