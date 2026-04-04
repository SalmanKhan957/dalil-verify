from __future__ import annotations

from domains.answer_engine.response_builder import build_explain_answer_payload


# Compatibility wrapper retained while imports are migrated.
def compose_explain_answer(plan, evidence):
    return build_explain_answer_payload(plan, evidence)
