import pytest

pytest.importorskip('sqlalchemy')

from domains.ask.planner import build_ask_plan
from domains.ask.route_types import AskRouteType


def _quran_state_payload() -> dict:
    return {
        'scope': {
            'domains': ['quran', 'tafsir'],
            'quran_ref': 'quran:2:255-256',
            'quran_span_ref': 'quran:2:255-256',
            'tafsir_source_ids': ['tafsir:tafheem-al-quran-en', 'tafsir:ibn-kathir-en'],
        },
        'anchors': {'refs': ['quran:2:255-256'], 'domains': ['quran', 'tafsir']},
        'followup_ready': True,
    }


def test_focus_source_uses_active_tafsir_source_scope() -> None:
    plan = build_ask_plan('What does Tafheem say?', request_context={'_hydrated_session_state': _quran_state_payload()})
    assert plan.route_type == AskRouteType.ANCHORED_FOLLOWUP_TAFSIR.value
    assert plan.followup_target_source_id == 'tafsir:tafheem-al-quran-en'


def test_focus_second_verse_uses_current_active_span() -> None:
    plan = build_ask_plan('What about the second verse?', request_context={'_hydrated_session_state': _quran_state_payload()})
    assert plan.route_type == AskRouteType.ANCHORED_FOLLOWUP_QURAN.value
    assert plan.followup_target_ref == 'quran:2:256'


def test_simplify_quran_followup_preserves_current_quran_anchor() -> None:
    plan = build_ask_plan('Say it more simply', request_context={'_hydrated_session_state': _quran_state_payload()})
    assert plan.followup_action_type == 'simplify'
    assert plan.active_scope_summary['quran_ref'] == 'quran:2:255-256'


def test_repeat_exact_text_returns_quote_mode_not_reexplain_mode() -> None:
    plan = build_ask_plan('Show the exact wording again', request_context={'_hydrated_session_state': _quran_state_payload()})
    assert plan.route_type == AskRouteType.ANCHORED_FOLLOWUP_QURAN.value
    assert plan.action_type == 'fetch_text'
