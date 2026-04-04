from __future__ import annotations

from domains.ask.planner_types import AbstentionReason


def build_unsupported_response(query: str, reason: AbstentionReason) -> dict[str, object]:
    return {'ok': False, 'query': query, 'error': reason.value}
