from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AnswerMode(str, Enum):
    EXPLAIN = "explain"
    FETCH_TEXT = "fetch_text"
    VERIFY = "verify"
    VERIFY_THEN_EXPLAIN = "verify_then_explain"
    ABSTAIN = "abstain"


class EvidenceDomain(str, Enum):
    QURAN = "quran"
    TAFSIR = "tafsir"


class AbstainReason(str, Enum):
    UNSUPPORTED_QUERY = "unsupported_query_type_for_now"
    COULD_NOT_RESOLVE_REFERENCE = "could_not_resolve_reference"
    REQUEST_OBJECT_REQUIRED = "request_object_required_for_verifier_workflow"
    SOURCE_POLICY_BLOCKED = "source_policy_blocked"
    TAFSIR_NOT_REQUESTED = "tafsir_not_requested"
    NO_USABLE_EVIDENCE = "no_usable_evidence"


@dataclass(slots=True)
class SourceInvocationPlan:
    domain: EvidenceDomain
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnswerPlan:
    mode: AnswerMode
    query: str
    route_type: str
    action_type: str
    quran_plan: SourceInvocationPlan | None = None
    tafsir_plan: SourceInvocationPlan | None = None
    allow_composition: bool = False
    tafsir_requested: bool = False
    tafsir_explicit: bool = False
    debug: bool = False
    abstain_reason: str | None = None
    route: dict[str, Any] = field(default_factory=dict)
