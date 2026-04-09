from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.query_intelligence.catalog import load_clarify_policies


@dataclass(frozen=True, slots=True)
class ClarifyInstruction:
    reason: str
    domain: str
    prompt: str
    suggested_topics: tuple[str, ...]


def build_clarify_instruction(*, reason: str, domain: str, concept_matches: list[str] | None = None) -> ClarifyInstruction | None:
    for policy in load_clarify_policies():
        if policy['reason'] != reason or policy['domain'] != domain:
            continue
        suggestions = list(policy.get('suggested_topics') or [])
        for concept in concept_matches or []:
            if concept and concept not in suggestions:
                suggestions.append(concept)
        return ClarifyInstruction(
            reason=reason,
            domain=domain,
            prompt=str(policy.get('prompt') or '').strip(),
            suggested_topics=tuple(suggestions),
        )
    return None


def serialize_clarify_instruction(instruction: ClarifyInstruction | None) -> dict[str, Any] | None:
    if instruction is None:
        return None
    return {
        'reason': instruction.reason,
        'domain': instruction.domain,
        'prompt': instruction.prompt,
        'suggested_topics': list(instruction.suggested_topics),
    }
