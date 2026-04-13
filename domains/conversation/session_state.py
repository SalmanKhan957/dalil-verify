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

    def to_payload(self) -> dict[str, Any]:
        return {
            'route_type': self.route_type,
            'answer_mode': self.answer_mode,
            'domains': list(self.domains),
            'quran_ref': self.quran_ref,
            'quran_span_ref': self.quran_span_ref,
            'tafsir_source_ids': list(self.tafsir_source_ids),
            'hadith_ref': self.hadith_ref,
            'hadith_source_id': self.hadith_source_id,
        }


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
            if ref and ref not in refs:
                refs.append(ref)
            if domain and domain not in domains:
                domains.append(domain)
        return cls(refs=refs, domains=domains)

    def to_payload(self) -> dict[str, Any]:
        return {'refs': list(self.refs), 'domains': list(self.domains)}


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

    def active_scope_summary(self) -> dict[str, Any]:
        return {
            'domains': list(self.scope.domains),
            'quran_ref': self.scope.quran_ref,
            'quran_span_ref': self.scope.quran_span_ref,
            'tafsir_source_ids': list(self.scope.tafsir_source_ids),
            'hadith_ref': self.scope.hadith_ref,
            'hadith_source_id': self.scope.hadith_source_id,
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            'conversation_id': self.conversation_id,
            'parent_turn_id': self.parent_turn_id,
            'turn_id': self.turn_id,
            'route_type': self.route_type,
            'answer_mode': self.answer_mode,
            'terminal_state': self.terminal_state,
            'scope': self.scope.to_payload(),
            'anchors': self.anchors.to_payload(),
            'citations': list(self.citations),
            'active_source_ids': list(self.active_source_ids),
            'followup_ready': bool(self.followup_ready),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None, *, raw_context: dict[str, Any] | None = None) -> "SessionState":
        payload = dict(payload or {})
        scope_payload = payload.get('scope') if isinstance(payload.get('scope'), dict) else {}
        anchors_payload = payload.get('anchors') if isinstance(payload.get('anchors'), dict) else {}
        return cls(
            conversation_id=str(payload.get('conversation_id') or '').strip() or None,
            parent_turn_id=str(payload.get('parent_turn_id') or '').strip() or None,
            turn_id=str(payload.get('turn_id') or '').strip() or None,
            route_type=str(payload.get('route_type') or '').strip() or None,
            answer_mode=str(payload.get('answer_mode') or '').strip() or None,
            terminal_state=str(payload.get('terminal_state') or '').strip() or None,
            scope=ActiveScope(
                route_type=str(scope_payload.get('route_type') or '').strip() or None,
                answer_mode=str(scope_payload.get('answer_mode') or '').strip() or None,
                domains=[str(item).strip() for item in list(scope_payload.get('domains') or []) if str(item).strip()],
                quran_ref=str(scope_payload.get('quran_ref') or '').strip() or None,
                quran_span_ref=str(scope_payload.get('quran_span_ref') or '').strip() or None,
                tafsir_source_ids=[str(item).strip() for item in list(scope_payload.get('tafsir_source_ids') or []) if str(item).strip()],
                hadith_ref=str(scope_payload.get('hadith_ref') or '').strip() or None,
                hadith_source_id=str(scope_payload.get('hadith_source_id') or '').strip() or None,
            ),
            anchors=ConversationAnchorSet(
                refs=[str(item).strip() for item in list(anchors_payload.get('refs') or []) if str(item).strip()],
                domains=[str(item).strip() for item in list(anchors_payload.get('domains') or []) if str(item).strip()],
            ),
            citations=[str(item).strip() for item in list(payload.get('citations') or []) if str(item).strip()],
            active_source_ids=[str(item).strip() for item in list(payload.get('active_source_ids') or []) if str(item).strip()],
            followup_ready=bool(payload.get('followup_ready')),
            raw_context=dict(raw_context or {}),
        )
