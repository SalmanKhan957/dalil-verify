from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .quran_followup import adjacent_ref, available_ordinals
from .session_state import SessionState


class FollowupAction(StrEnum):
    FOCUS_SOURCE = "focus_source"
    SELECT_QURAN_VERSE = "select_quran_verse"
    NAVIGATE_NEXT_VERSE = "navigate_next_verse"
    NAVIGATE_PREVIOUS_VERSE = "navigate_previous_verse"
    SIMPLIFY = "simplify"
    SUMMARIZE_HADITH = "summarize_hadith"
    EXTRACT_HADITH_LESSON = "extract_hadith_lesson"
    REPEAT_EXACT_TEXT = "repeat_exact_text"


@dataclass(slots=True)
class FollowupCapability:
    action_type: FollowupAction
    target_domain: str
    target_source_id: str | None = None
    target_ref: str | None = None
    phrase_params: dict[str, str] = field(default_factory=dict)
    priority: int = 100


@dataclass(slots=True)
class FollowupCapabilitySet:
    capabilities: list[FollowupCapability] = field(default_factory=list)

    def add(self, capability: FollowupCapability) -> None:
        if capability not in self.capabilities:
            self.capabilities.append(capability)

    def sorted(self) -> list[FollowupCapability]:
        return sorted(self.capabilities, key=lambda item: (item.priority, item.action_type.value, item.target_source_id or '', item.target_ref or ''))


_SOURCE_LABEL_OVERRIDES = {
    'tafsir:tafheem-al-quran-en': 'Tafheem',
    'tafsir:ibn-kathir-en': 'Ibn Kathir',
    'tafsir:maarif-al-quran-en': "Ma'arif",
}


def _source_label(source_id: str) -> str:
    if source_id in _SOURCE_LABEL_OVERRIDES:
        return _SOURCE_LABEL_OVERRIDES[source_id]
    return source_id.split(':', 1)[-1].replace('-en', '').replace('-', ' ').title()


def derive_followup_capabilities(state: SessionState) -> FollowupCapabilitySet:
    result = FollowupCapabilitySet()

    if not state.supports_followups():
        return result

    if state.has_quran_scope():
        comparative_source_ids = list(state.scope.effective_tafsir_source_ids())
        current_tafsir_source_id = str(state.scope.current_tafsir_source_id or '').strip() or None
        for idx, source_id in enumerate(comparative_source_ids):
            if current_tafsir_source_id and source_id == current_tafsir_source_id:
                continue
            result.add(
                FollowupCapability(
                    action_type=FollowupAction.FOCUS_SOURCE,
                    target_domain="tafsir",
                    target_source_id=source_id,
                    target_ref=state.scope.quran_ref,
                    phrase_params={"source_label": _source_label(source_id)},
                    priority=10 + idx,
                )
            )
        for offset, (ordinal, target_ref) in enumerate(available_ordinals(state.scope.quran_span_ref), start=0):
            result.add(
                FollowupCapability(
                    action_type=FollowupAction.SELECT_QURAN_VERSE,
                    target_domain="quran",
                    target_ref=target_ref,
                    phrase_params={"ordinal": ordinal},
                    priority=20 + offset,
                )
            )
        previous_ref = adjacent_ref(state.scope.quran_ref or state.scope.quran_span_ref, 'previous')
        if previous_ref is not None:
            result.add(
                FollowupCapability(
                    action_type=FollowupAction.NAVIGATE_PREVIOUS_VERSE,
                    target_domain="quran",
                    target_ref=previous_ref,
                    phrase_params={"direction": 'previous'},
                    priority=30,
                )
            )
        next_ref = adjacent_ref(state.scope.quran_ref or state.scope.quran_span_ref, 'next')
        if next_ref is not None:
            result.add(
                FollowupCapability(
                    action_type=FollowupAction.NAVIGATE_NEXT_VERSE,
                    target_domain="quran",
                    target_ref=next_ref,
                    phrase_params={"direction": 'next'},
                    priority=31,
                )
            )
        result.add(
            FollowupCapability(
                action_type=FollowupAction.SIMPLIFY,
                target_domain="tafsir" if state.has_tafsir_scope() else "quran",
                target_ref=state.scope.quran_ref or state.scope.quran_span_ref,
                priority=40,
            )
        )
        result.add(
            FollowupCapability(
                action_type=FollowupAction.REPEAT_EXACT_TEXT,
                target_domain="quran",
                target_ref=state.scope.quran_ref or state.scope.quran_span_ref,
                priority=50,
            )
        )

    if state.has_hadith_scope():
        result.add(
            FollowupCapability(
                action_type=FollowupAction.SUMMARIZE_HADITH,
                target_domain="hadith",
                target_source_id=state.scope.hadith_source_id,
                target_ref=state.scope.hadith_ref,
                priority=10,
            )
        )
        result.add(
            FollowupCapability(
                action_type=FollowupAction.EXTRACT_HADITH_LESSON,
                target_domain="hadith",
                target_source_id=state.scope.hadith_source_id,
                target_ref=state.scope.hadith_ref,
                priority=20,
            )
        )
        result.add(
            FollowupCapability(
                action_type=FollowupAction.REPEAT_EXACT_TEXT,
                target_domain="hadith",
                target_source_id=state.scope.hadith_source_id,
                target_ref=state.scope.hadith_ref,
                priority=30,
            )
        )

    return result
