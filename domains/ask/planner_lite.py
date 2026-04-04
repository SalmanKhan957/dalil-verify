from __future__ import annotations

from domains.ask.planner import build_ask_plan


# Compatibility wrapper retained while imports are migrated.
def build_answer_plan(*args, **kwargs):
    return build_ask_plan(*args, **kwargs)
