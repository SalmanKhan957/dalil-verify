from __future__ import annotations

from typing import Any

from domains.ask.planner_types import AskPlan
from domains.ask.route_types import AskRouteType


_CONTROL_STATUS_ENFORCED = "enforced"
_CONTROL_STATUS_ADVISORY = "advisory_only"
_CONTROL_STATUS_ALIAS = "compatibility_alias"


def _status(*, status: str, canonical_field: str | None = None, notes: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": status}
    if canonical_field is not None:
        payload["canonical_field"] = canonical_field
    if notes is not None:
        payload["notes"] = notes
    return payload


def build_request_control_honesty(plan: AskPlan) -> dict[str, Any]:
    anchored_followup_routes = {
        AskRouteType.ANCHORED_FOLLOWUP_QURAN.value,
        AskRouteType.ANCHORED_FOLLOWUP_TAFSIR.value,
        AskRouteType.ANCHORED_FOLLOWUP_HADITH.value,
    }
    resolution_mode = str((plan.request_context or {}).get('_anchor_resolution_mode') or 'none')
    anchor_status = _CONTROL_STATUS_ENFORCED if (plan.route_type in anchored_followup_routes or resolution_mode in {'request_supplied', 'parent_turn_hydrated', 'conversation_hydrated', 'implicit_session_hydrated'}) else _CONTROL_STATUS_ADVISORY
    anchor_notes = (
        'Used by the planner/runtime for narrow anchored follow-up resolution over Quran, Tafsir, and explicit Hadith anchors.'
        if anchor_status == _CONTROL_STATUS_ENFORCED
        else 'Accepted and surfaced for future follow-up support, but not yet used by the planner/runtime to resolve follow-up questions.'
    )
    if resolution_mode == 'parent_turn_hydrated':
        conversation_status = _CONTROL_STATUS_ADVISORY
        conversation_notes = 'Conversation-level state remains bounded; parent-turn hydration resolved the active follow-up anchor set for this request.'
        parent_turn_status = _CONTROL_STATUS_ENFORCED
        parent_turn_notes = 'Used by the planner/runtime to hydrate anchors from the immediately referenced prior turn for narrow anchored follow-up.'
    elif resolution_mode == 'conversation_hydrated':
        conversation_status = _CONTROL_STATUS_ENFORCED
        conversation_notes = 'Used by the planner/runtime to hydrate the latest follow-up-eligible anchors for this explicit conversation.'
        parent_turn_status = _CONTROL_STATUS_ADVISORY
        parent_turn_notes = 'Accepted and surfaced for future parent-turn targeting, but not required for this request.'
    elif resolution_mode == 'implicit_session_hydrated':
        conversation_status = _CONTROL_STATUS_ENFORCED
        conversation_notes = 'Used by the planner/runtime to hydrate the latest follow-up-eligible anchors for the current client session when no explicit anchors were supplied.'
        parent_turn_status = _CONTROL_STATUS_ADVISORY
        parent_turn_notes = 'Accepted and surfaced for future parent-turn targeting, but not required for this request.'
    else:
        conversation_status = _CONTROL_STATUS_ADVISORY
        conversation_notes = 'Accepted and surfaced for follow-up support. Latest-anchor hydration is available for narrow anchored follow-up when a conversation id or stable client session is present.'
        parent_turn_status = _CONTROL_STATUS_ADVISORY
        parent_turn_notes = 'Accepted and surfaced for follow-up support. Parent-turn hydration is available when the caller supplies a prior turn id emitted by the conversation surface.'
    return {
        "context": {
            "conversation_id": _status(
                status=conversation_status,
                notes=conversation_notes,
            ),
            "parent_turn_id": _status(
                status=parent_turn_status,
                notes=parent_turn_notes,
            ),
            "anchor_refs": _status(
                status=anchor_status,
                notes=anchor_notes,
            ),
        },
        "preferences": {
            "language": _status(
                status=_CONTROL_STATUS_ADVISORY,
                notes="Accepted as an answer-shaping hint, but bounded answer rendering does not yet guarantee language switching.",
            ),
            "verbosity": _status(
                status=_CONTROL_STATUS_ADVISORY,
                notes="Accepted as an answer-shaping hint, but bounded answer rendering does not yet guarantee verbosity changes.",
            ),
            "citations": _status(
                status=_CONTROL_STATUS_ADVISORY,
                notes="Accepted as an answer-shaping hint, but bounded answer rendering does not yet guarantee citation-layout changes.",
            ),
        },
        "sources": {
            "quran": {
                "text_source_id": _status(status=_CONTROL_STATUS_ENFORCED),
                "translation_source_id": _status(status=_CONTROL_STATUS_ENFORCED),
            },
            "tafsir": {
                "mode": _status(status=_CONTROL_STATUS_ENFORCED),
                "limit": _status(
                    status=_CONTROL_STATUS_ENFORCED,
                    notes="Used only when Tafsir retrieval is eligible and selected for the request.",
                ),
                "source_ids": _status(
                    status=_CONTROL_STATUS_ENFORCED,
                    notes="Current public contract supports up to three Tafsir source ids for source-separated comparative Quran commentary selection.",
                ),
            },
            "hadith": {
                "mode": _status(
                    status=_CONTROL_STATUS_ENFORCED,
                    notes="Current public contract supports bounded explicit Hadith lookup/explain lanes and bounded topical Hadith retrieval. This mode is enforced within that public bounded scope; unrestricted multi-source Hadith answering remains unsupported.",
                ),
                "collection_ids": _status(
                    status=_CONTROL_STATUS_ENFORCED,
                    notes="Current public contract supports at most one Hadith collection id; multi-collection selection is deferred.",
                ),
            },
        },
        "diagnostics": {
            "debug": _status(status=_CONTROL_STATUS_ENFORCED),
        },
        "legacy_aliases": {
            "include_tafsir": _status(
                status=_CONTROL_STATUS_ALIAS,
                canonical_field="sources.tafsir.mode",
                notes="Legacy flat compatibility field translated into canonical nested source controls.",
            ),
            "tafsir_source_id": _status(
                status=_CONTROL_STATUS_ALIAS,
                canonical_field="sources.tafsir.source_ids[0]",
                notes="Legacy flat compatibility field translated into canonical nested source controls.",
            ),
            "tafsir_limit": _status(
                status=_CONTROL_STATUS_ALIAS,
                canonical_field="sources.tafsir.limit",
                notes="Legacy flat compatibility field translated into canonical nested source controls.",
            ),
            "quran_text_source_id": _status(
                status=_CONTROL_STATUS_ALIAS,
                canonical_field="sources.quran.text_source_id",
                notes="Legacy flat compatibility field translated into canonical nested source controls.",
            ),
            "quran_translation_source_id": _status(
                status=_CONTROL_STATUS_ALIAS,
                canonical_field="sources.quran.translation_source_id",
                notes="Legacy flat compatibility field translated into canonical nested source controls.",
            ),
            "hadith_source_id": _status(
                status=_CONTROL_STATUS_ALIAS,
                canonical_field="sources.hadith.collection_ids[0]",
                notes="Legacy flat compatibility field translated into canonical nested source controls.",
            ),
            "debug": _status(
                status=_CONTROL_STATUS_ALIAS,
                canonical_field="diagnostics.debug",
                notes="Legacy flat compatibility field translated into canonical diagnostics controls.",
            ),
        },
    }
