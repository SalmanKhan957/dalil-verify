from services.answer_engine.abstention import infer_unsupported_abstention_reason, reason_to_error_code
from services.answer_engine.plan_types import AbstentionReason



def test_infer_unsupported_abstention_reason_detects_hadith() -> None:
    reason = infer_unsupported_abstention_reason("Give me hadith about patience")
    assert reason == AbstentionReason.HADITH_NOT_SUPPORTED_YET
    assert reason_to_error_code(reason) == "hadith_not_supported_yet"



def test_infer_unsupported_abstention_reason_detects_topical_islam_query() -> None:
    reason = infer_unsupported_abstention_reason("What does Islam say about anxiety?")
    assert reason == AbstentionReason.UNSUPPORTED_CAPABILITY



def test_infer_unsupported_abstention_reason_detects_clarification_needed() -> None:
    reason = infer_unsupported_abstention_reason("")
    assert reason == AbstentionReason.NEEDS_CLARIFICATION
