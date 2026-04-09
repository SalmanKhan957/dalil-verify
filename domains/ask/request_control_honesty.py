from __future__ import annotations

from typing import Any

from domains.ask.planner_types import AskPlan


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
    return {
        "context": {
            "conversation_id": _status(
                status=_CONTROL_STATUS_ADVISORY,
                notes="Accepted and surfaced for future follow-up support, but not yet used by the planner/runtime for stateful resolution.",
            ),
            "parent_turn_id": _status(
                status=_CONTROL_STATUS_ADVISORY,
                notes="Accepted and surfaced for future follow-up support, but not yet used by the planner/runtime for parent-turn resolution.",
            ),
            "anchor_refs": _status(
                status=_CONTROL_STATUS_ADVISORY,
                notes="Accepted and surfaced for future follow-up support, but not yet used by the planner/runtime to resolve follow-up questions.",
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
                    notes="Current public contract supports at most one Tafsir source id; multi-source selection is deferred.",
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
