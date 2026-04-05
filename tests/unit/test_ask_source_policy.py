from domains.ask.route_types import AskRouteType
from domains.policies.ask_source_policy import evaluate_ask_source_policy
from domains.source_registry.registry import get_source_record



def test_evaluate_ask_source_policy_selects_default_tafsir_for_query_intent() -> None:
    quran_source = get_source_record('quran:tanzil-simple')

    policy = evaluate_ask_source_policy(
        route_type=AskRouteType.EXPLICIT_QURAN_REFERENCE.value,
        action_type='explain',
        include_tafsir=None,
        tafsir_intent_detected=True,
        requested_tafsir_source_id=None,
        quran_source=quran_source,
        requested_quran_text_source_id='quran:tanzil-simple',
        requested_quran_translation_source_id='quran:towards-understanding-en',
        selected_quran_text_source_id='quran:tanzil-simple',
        selected_quran_translation_source_id='quran:towards-understanding-en',
        quran_text_source_origin='implicit_default',
        quran_translation_source_origin='implicit_default',
    )

    assert policy.quran.allowed is True
    assert policy.quran.policy_reason == 'selected'
    assert policy.quran.text_source_origin == 'implicit_default'
    assert policy.quran.translation_source_origin == 'implicit_default'
    assert policy.tafsir.requested is True
    assert policy.tafsir.request_origin == 'query_intent'
    assert policy.tafsir.allowed is True
    assert policy.tafsir.included is True
    assert policy.tafsir.selected_source_id == 'tafsir:ibn-kathir-en'
    assert policy.tafsir.policy_reason == 'selected'



def test_evaluate_ask_source_policy_honors_explicit_suppression() -> None:
    quran_source = get_source_record('quran:tanzil-simple')

    policy = evaluate_ask_source_policy(
        route_type=AskRouteType.EXPLICIT_QURAN_REFERENCE.value,
        action_type='explain',
        include_tafsir=False,
        tafsir_intent_detected=True,
        requested_tafsir_source_id='tafsir:ibn-kathir-en',
        quran_source=quran_source,
        requested_quran_text_source_id='quran:tanzil-simple',
        requested_quran_translation_source_id='quran:towards-understanding-en',
        selected_quran_text_source_id='quran:tanzil-simple',
        selected_quran_translation_source_id='quran:towards-understanding-en',
        quran_text_source_origin='explicit_override',
        quran_translation_source_origin='explicit_override',
    )

    assert policy.tafsir.requested is False
    assert policy.tafsir.request_origin == 'explicit_suppression'
    assert policy.tafsir.included is False
    assert policy.tafsir.policy_reason == 'suppressed_by_request'
    assert policy.quran.text_source_origin == 'explicit_override'
    assert policy.quran.translation_source_origin == 'explicit_override'



def test_evaluate_ask_source_policy_marks_non_eligible_route() -> None:
    quran_source = get_source_record('quran:tanzil-simple')

    policy = evaluate_ask_source_policy(
        route_type=AskRouteType.ARABIC_QURAN_QUOTE.value,
        action_type='verify_source',
        include_tafsir=True,
        tafsir_intent_detected=False,
        requested_tafsir_source_id='tafsir:ibn-kathir-en',
        quran_source=quran_source,
        requested_quran_text_source_id='quran:tanzil-simple',
        requested_quran_translation_source_id='quran:towards-understanding-en',
        selected_quran_text_source_id='quran:tanzil-simple',
        selected_quran_translation_source_id='quran:towards-understanding-en',
        quran_text_source_origin='implicit_default',
        quran_translation_source_origin='implicit_default',
    )

    assert policy.tafsir.allowed is False
    assert policy.tafsir.included is False
    assert policy.tafsir.policy_reason == 'route_not_eligible_for_tafsir'



def test_evaluate_ask_source_policy_allows_tafsir_for_arabic_quote_explain_flow() -> None:
    quran_source = get_source_record('quran:tanzil-simple')

    policy = evaluate_ask_source_policy(
        route_type=AskRouteType.ARABIC_QURAN_QUOTE.value,
        action_type='verify_then_explain',
        include_tafsir=None,
        tafsir_intent_detected=True,
        requested_tafsir_source_id=None,
        quran_source=quran_source,
        requested_quran_text_source_id='quran:tanzil-simple',
        requested_quran_translation_source_id='quran:towards-understanding-en',
        selected_quran_text_source_id='quran:tanzil-simple',
        selected_quran_translation_source_id='quran:towards-understanding-en',
        quran_text_source_origin='implicit_default',
        quran_translation_source_origin='implicit_default',
    )

    assert policy.tafsir.requested is True
    assert policy.tafsir.request_origin == 'query_intent'
    assert policy.tafsir.allowed is True
    assert policy.tafsir.included is True
    assert policy.tafsir.selected_source_id == 'tafsir:ibn-kathir-en'
    assert policy.tafsir.policy_reason == 'selected'
