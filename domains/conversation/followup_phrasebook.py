from __future__ import annotations

from .followup_capabilities import FollowupAction, FollowupCapabilitySet


def render_suggested_followups(capability_set: FollowupCapabilitySet) -> list[str]:
    """Presentation layer only.

    The typed capability graph is the truth layer.
    These strings are just the user-facing phrasing.
    """

    suggestions: list[str] = []
    for item in capability_set.sorted():
        if item.action_type == FollowupAction.FOCUS_SOURCE:
            source_label = item.phrase_params.get("source_label") or "this source"
            suggestions.append(f"What does {source_label} say?")
        elif item.action_type == FollowupAction.FOCUS_SECOND_VERSE:
            suggestions.append("What about the second verse?")
        elif item.action_type == FollowupAction.SIMPLIFY:
            suggestions.append("Say it more simply")
        elif item.action_type == FollowupAction.SUMMARIZE_HADITH:
            suggestions.append("Summarize this hadith")
        elif item.action_type == FollowupAction.EXTRACT_HADITH_LESSON:
            suggestions.append("What lesson does this hadith teach?")
        elif item.action_type == FollowupAction.REPEAT_EXACT_TEXT:
            suggestions.append("Show the exact wording again")
    return suggestions
