from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .session_state import SessionState


class FollowupAction(StrEnum):
    FOCUS_SOURCE = "focus_source"
    FOCUS_SECOND_VERSE = "focus_second_verse"
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
        return sorted(self.capabilities, key=lambda item: item.priority)


def derive_followup_capabilities(state: SessionState) -> FollowupCapabilitySet:
    result = FollowupCapabilitySet()

    if not state.supports_followups():
        return result

    if state.has_quran_scope():
        result.add(
            FollowupCapability(
                action_type=FollowupAction.SIMPLIFY,
                target_domain="quran",
                target_ref=state.scope.quran_ref,
                priority=40,
            )
        )
        result.add(
            FollowupCapability(
                action_type=FollowupAction.FOCUS_SECOND_VERSE,
                target_domain="quran",
                target_ref=state.scope.quran_span_ref,
                priority=20,
            )
        )
        for idx, source_id in enumerate(state.scope.tafsir_source_ids):
            label = source_id.split(":", 1)[-1].replace("-en", "").replace("-", " ").title()
            result.add(
                FollowupCapability(
                    action_type=FollowupAction.FOCUS_SOURCE,
                    target_domain="tafsir",
                    target_source_id=source_id,
                    target_ref=state.scope.quran_ref,
                    phrase_params={"source_label": label},
                    priority=10 + idx,
                )
            )
        result.add(
            FollowupCapability(
                action_type=FollowupAction.REPEAT_EXACT_TEXT,
                target_domain="quran",
                target_ref=state.scope.quran_ref,
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
