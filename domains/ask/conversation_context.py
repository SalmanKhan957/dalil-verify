"""Deprecated compatibility placeholder for earlier follow-up plans.

Live continuity state is handled by ``domains.conversation.anchor_store`` via
session/turn anchor hydration. This module remains only to avoid breaking any
stray imports while the legacy placeholder is retired deliberately.
"""

from dataclasses import dataclass, field


@dataclass(slots=True)
class ConversationContext:
    """Legacy no-op context shell retained for import stability only."""

    last_route_type: str | None = None
    last_citation: str | None = None
    notes: list[str] = field(default_factory=list)
