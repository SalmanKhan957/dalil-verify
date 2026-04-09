from domains.ask.classifier import classify_ask_query
from domains.ask.planner import build_ask_plan
from domains.ask.planner_types import ResponseMode
from domains.answer_engine.execution import execute_plan
from domains.answer_engine.response_builder import build_explain_answer_payload


def test_classifier_surfaces_clarify_metadata_for_broad_hadith_query() -> None:
    route = classify_ask_query('How can I improve myself according to hadith?')
    assert route['route_type'] == 'unsupported_for_now'
    assert route['needs_clarification'] is True
    assert route['clarify']['prompt']
    assert 'anger' in route['clarify']['suggested_topics']


def test_planner_builds_clarify_mode_from_broad_hadith_query() -> None:
    route = classify_ask_query('How can I improve myself according to hadith?')
    plan = build_ask_plan('How can I improve myself according to hadith?', route=route)
    assert plan.response_mode == ResponseMode.CLARIFY
    assert plan.should_abstain is False
    assert plan.clarify_prompt
    assert 'patience' in plan.clarify_topics


def test_response_builder_returns_clarify_answer_without_error() -> None:
    route = classify_ask_query('How can I improve myself according to hadith?')
    plan = build_ask_plan('How can I improve myself according to hadith?', route=route)
    evidence = execute_plan(plan)
    payload = build_explain_answer_payload(plan, evidence)
    assert payload['ok'] is True
    assert payload['answer_mode'] == 'clarify'
    assert payload['error'] is None
    assert payload['answer_text']
    assert 'clarification_required' in payload['warnings']
