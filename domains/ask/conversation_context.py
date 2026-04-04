"""Thin conversation-context placeholder for future follow-up support."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class ConversationContext:
    last_route_type: str | None = None
    last_citation: str | None = None
    notes: list[str] = field(default_factory=list)
