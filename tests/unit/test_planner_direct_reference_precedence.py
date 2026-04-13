from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

from domains.ask.planner import build_ask_plan
from domains.ask.route_types import AskRouteType


def test_explicit_surah_reference_overrides_implicit_hydrated_followup_state() -> None:
    state_payload = {
        "scope": {
            "domains": ["quran", "tafsir"],
            "quran_ref": "quran:2:255",
            "quran_span_ref": "quran:2:255",
            "tafsir_source_ids": [
                "tafsir:ibn-kathir-en",
                "tafsir:maarif-al-quran-en",
                "tafsir:tafheem-al-quran-en",
            ],
        },
        "anchors": {
            "refs": [
                "quran:2:255",
                "tafsir:ibn-kathir-en:82802",
                "tafsir:maarif-al-quran-en:79799",
                "tafsir:tafheem-al-quran-en:2:255",
            ],
            "domains": ["quran", "tafsir"],
        },
        "followup_ready": True,
    }

    plan = build_ask_plan(
        "Ibn Kathir on Surah Al-Ikhlas",
        include_tafsir=True,
        tafsir_source_id="tafsir:ibn-kathir-en",
        request_context={"_hydrated_session_state": state_payload},
    )

    assert plan.route_type == AskRouteType.EXPLICIT_QURAN_REFERENCE.value
    assert plan.followup_action_type is None
    assert plan.followup_reason is None
    assert plan.resolved_quran_ref is not None
    assert plan.resolved_quran_ref["canonical_source_id"] == "quran:112:1-4"
    assert plan.source_policy is not None
    assert plan.source_policy.tafsir.selected_source_ids == ["tafsir:ibn-kathir-en"]
