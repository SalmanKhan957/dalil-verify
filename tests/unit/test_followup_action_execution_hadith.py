import pytest

pytest.importorskip('sqlalchemy')

from domains.ask.planner import build_ask_plan
from domains.ask.route_types import AskRouteType


def _hadith_state_payload() -> dict:
    return {
        'scope': {
            'domains': ['hadith'],
            'hadith_ref': 'hadith:sahih-al-bukhari-en:7',
            'hadith_source_id': 'hadith:sahih-al-bukhari-en',
        },
        'anchors': {'refs': ['hadith:sahih-al-bukhari-en:7'], 'domains': ['hadith']},
        'followup_ready': True,
    }


def test_summarize_hadith_uses_active_explicit_hadith_ref() -> None:
    plan = build_ask_plan('Summarize this hadith', request_context={'_hydrated_session_state': _hadith_state_payload()})
    assert plan.route_type == AskRouteType.ANCHORED_FOLLOWUP_HADITH.value
    assert plan.followup_target_ref == 'hadith:sahih-al-bukhari-en:7'


def test_extract_hadith_lesson_stays_in_hadith_domain() -> None:
    plan = build_ask_plan('What lesson does this hadith teach?', request_context={'_hydrated_session_state': _hadith_state_payload()})
    assert plan.route_type == AskRouteType.ANCHORED_FOLLOWUP_HADITH.value
    assert plan.followup_target_domain == 'hadith'


def test_repeat_exact_text_hadith_reuses_active_hadith_ref() -> None:
    plan = build_ask_plan('Show the exact wording again', request_context={'_hydrated_session_state': _hadith_state_payload()})
    assert plan.route_type == AskRouteType.ANCHORED_FOLLOWUP_HADITH.value
    assert plan.followup_target_ref == 'hadith:sahih-al-bukhari-en:7'
