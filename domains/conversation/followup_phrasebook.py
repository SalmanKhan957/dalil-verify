from __future__ import annotations

from .followup_capabilities import FollowupAction, FollowupCapabilitySet


def render_suggested_followups(capability_set: FollowupCapabilitySet, *, limit: int = 4) -> list[str]:
    """Presentation layer only.

    The typed capability graph is the truth layer.
    These strings are just the user-facing phrasing.
    """

    suggestions: list[str] = []
    seen: set[str] = set()
    for item in capability_set.sorted():
        phrase: str | None = None
        if item.action_type == FollowupAction.FOCUS_SOURCE:
            source_label = item.phrase_params.get("source_label") or "this source"
            phrase = f"What does {source_label} say?"
        elif item.action_type == FollowupAction.FOCUS_SECOND_VERSE:
            phrase = "What about the second verse?"
        elif item.action_type == FollowupAction.SIMPLIFY:
            phrase = "Say it more simply"
        elif item.action_type == FollowupAction.SUMMARIZE_HADITH:
            phrase = "Summarize this hadith"
        elif item.action_type == FollowupAction.EXTRACT_HADITH_LESSON:
            phrase = "What lesson does this hadith teach?"
        elif item.action_type == FollowupAction.REPEAT_EXACT_TEXT:
            phrase = "Show the exact wording again"
        if not phrase or phrase in seen:
            continue
        seen.add(phrase)
        suggestions.append(phrase)
        if len(suggestions) >= limit:
            break
    return suggestions
