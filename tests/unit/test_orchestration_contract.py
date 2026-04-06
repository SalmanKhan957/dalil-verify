from domains.answer_engine.execution import execute_plan
from domains.answer_engine.response_builder import build_explain_answer_payload
from domains.ask.planner import build_ask_plan


def test_debug_payload_surfaces_canonical_orchestration_contract() -> None:
    plan = build_ask_plan('112:1-2', include_tafsir=False, debug=True, repository_mode='csv', request_context={'conversation_id': 'conv_1', 'parent_turn_id': 'turn_0', 'anchor_refs': ['quran:112:1-2']}, request_preferences={'language': 'en', 'verbosity': 'standard', 'citations': 'inline'}, source_controls={'tafsir': {'mode': 'off', 'limit': 3, 'source_ids': []}}, request_contract_version='ask.vnext')
    evidence = execute_plan(plan)
    payload = build_explain_answer_payload(plan, evidence)
    assert payload['ok'] is True
    assert payload['orchestration'] is not None
    orchestration = payload['orchestration']
    assert orchestration['request']['query'] == '112:1-2'
    assert orchestration['interpretation']['primary_intent'] == 'source_grounded_quran_explanation'
    assert orchestration['plan']['selected_domains'] == ['quran']
    assert orchestration['conversation']['followup_ready'] is True
    assert orchestration['evidence'][0]['evidence_type'] == 'quran_span'
    assert payload['debug']['orchestration'] == orchestration

    assert orchestration['request']['contract_version'] == 'ask.vnext'
    assert orchestration['request']['context']['conversation_id'] == 'conv_1'
    assert orchestration['request']['preferences']['language'] == 'en'
    assert orchestration['request']['sources']['tafsir']['mode'] == 'off'
    assert orchestration['request']['control_honesty']['preferences']['language']['status'] == 'advisory_only'
    assert orchestration['request']['control_honesty']['sources']['quran']['text_source_id']['status'] == 'enforced'
    assert orchestration['diagnostics']['response_surface_contract']['notes']['result'].startswith('Legacy compatibility envelope')
    assert payload['conversation']['followup_ready'] is True
