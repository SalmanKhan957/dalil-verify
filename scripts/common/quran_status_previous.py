from __future__ import annotations

from collections.abc import Mapping
from typing import Any

STATUS_RANK: dict[str, int] = {
    "Cannot assess": 0,
    "No reliable match found in current corpus": 1,
    "Close / partial match found": 2,
    "Exact match found": 3,
}


def get_status_rank(status: str | None) -> int:
    return STATUS_RANK.get((status or "").strip(), 0)


def get_result_status_rank(result: Mapping[str, Any] | None) -> int:
    if not result:
        return 0
    return get_status_rank(str(result.get("match_status", "")))
