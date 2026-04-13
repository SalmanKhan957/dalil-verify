import pytest

pytest.importorskip('sqlalchemy')

from domains.ask.planner import build_ask_plan
from domains.ask.route_types import AskRouteType
from domains.ask.planner_types import ResponseMode



def test_planner_uses_hydrated_session_state_for_simplify_followup() -> None:
    state_payload = {
        'scope': {
            'domains': ['quran', 'tafsir'],
            'quran_ref': 'quran:112:1-4',
            'quran_span_ref': 'quran:112:1-4',
            'tafsir_source_ids': ['tafsir:tafheem-al-quran-en', 'tafsir:ibn-kathir-en'],
        },
        'anchors': {'refs': ['quran:112:1-4'], 'domains': ['quran', 'tafsir']},
        'followup_ready': True,
    }
    plan = build_ask_plan('Say it more simply', request_context={'_hydrated_session_state': state_payload})

    assert plan.route_type == AskRouteType.ANCHORED_FOLLOWUP_TAFSIR.value
    assert plan.followup_action_type == 'simplify'
    assert plan.response_mode in {ResponseMode.QURAN_WITH_TAFSIR, ResponseMode.ABSTAIN}



def test_planner_uses_hydrated_session_state_for_hadith_repeat_text() -> None:
    state_payload = {
        'scope': {
            'domains': ['hadith'],
            'hadith_ref': 'hadith:sahih-al-bukhari-en:7',
            'hadith_source_id': 'hadith:sahih-al-bukhari-en',
        },
        'anchors': {'refs': ['hadith:sahih-al-bukhari-en:7'], 'domains': ['hadith']},
        'followup_ready': True,
    }
    plan = build_ask_plan('Show the exact wording again', request_context={'_hydrated_session_state': state_payload})

    assert plan.route_type == AskRouteType.ANCHORED_FOLLOWUP_HADITH.value
    assert plan.followup_action_type == 'repeat_exact_text'
