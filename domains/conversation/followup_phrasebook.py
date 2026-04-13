from __future__ import annotations

from .followup_capabilities import FollowupAction, FollowupCapabilitySet


_ORDINAL_LABELS = {
    'first': 'first',
    'second': 'second',
    'third': 'third',
    'fourth': 'fourth',
    'last': 'last',
}


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
        elif item.action_type == FollowupAction.SELECT_QURAN_VERSE:
            ordinal = _ORDINAL_LABELS.get(item.phrase_params.get('ordinal', ''), item.phrase_params.get('ordinal', 'second'))
            phrase = f"What about the {ordinal} verse?"
        elif item.action_type == FollowupAction.NAVIGATE_NEXT_VERSE:
            phrase = "What about the next verse?"
        elif item.action_type == FollowupAction.NAVIGATE_PREVIOUS_VERSE:
            phrase = "What about the previous verse?"
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
