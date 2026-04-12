from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(slots=True)
class ActiveScope:
    """Bounded conversational scope for the current /ask thread.

    This is intentionally narrow. It does not model generic chat memory.
    It only carries the active evidence scope needed for source-grounded follow-ups.
    """

    route_type: str | None = None
    answer_mode: str | None = None
    domains: list[str] = field(default_factory=list)
    quran_ref: str | None = None
    quran_span_ref: str | None = None
    tafsir_source_ids: list[str] = field(default_factory=list)
    hadith_ref: str | None = None
    hadith_source_id: str | None = None


@dataclass(slots=True)
class ConversationAnchorSet:
    refs: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)

    @classmethod
    def from_anchor_payload(cls, anchors: Iterable[dict[str, Any]] | None) -> "ConversationAnchorSet":
        refs: list[str] = []
        domains: list[str] = []
        for anchor in anchors or []:
            if not isinstance(anchor, dict):
                continue
            ref = str(anchor.get("canonical_ref") or "").strip()
            domain = str(anchor.get("source_domain") or "").strip()
            if ref:
                refs.append(ref)
            if domain and domain not in domains:
                domains.append(domain)
        return cls(refs=refs, domains=domains)


@dataclass(slots=True)
class SessionState:
    """State derived from the latest /ask response and caller context.

    Keep this bounded and product-focused. This is not user memory.
    """

    conversation_id: str | None = None
    parent_turn_id: str | None = None
    turn_id: str | None = None
    route_type: str | None = None
    answer_mode: str | None = None
    terminal_state: str | None = None
    scope: ActiveScope = field(default_factory=ActiveScope)
    anchors: ConversationAnchorSet = field(default_factory=ConversationAnchorSet)
    citations: list[str] = field(default_factory=list)
    active_source_ids: list[str] = field(default_factory=list)
    followup_ready: bool = False
    raw_context: dict[str, Any] = field(default_factory=dict)

    def has_domain(self, domain: str) -> bool:
        return domain in self.scope.domains or domain in self.anchors.domains

    def has_quran_scope(self) -> bool:
        return bool(self.scope.quran_ref or self.scope.quran_span_ref)

    def has_hadith_scope(self) -> bool:
        return bool(self.scope.hadith_ref)

    def has_tafsir_scope(self) -> bool:
        return bool(self.scope.tafsir_source_ids)

    def supports_followups(self) -> bool:
        return bool(self.followup_ready and self.anchors.refs)
