from services.answer_engine.plan_types import AnswerMode, EvidenceDomain
from services.answer_engine.planner_lite import build_answer_plan



def test_build_answer_plan_adds_tafsir_for_tafsir_intent() -> None:
    plan = build_answer_plan("Tafsir of Surah Ikhlas")

    assert plan.mode == AnswerMode.EXPLAIN
    assert plan.quran_plan is not None
    assert plan.quran_plan.domain == EvidenceDomain.QURAN
    assert plan.tafsir_plan is not None
    assert plan.tafsir_plan.domain == EvidenceDomain.TAFSIR
    assert plan.allow_composition is True



def test_build_answer_plan_keeps_plain_reference_quran_only() -> None:
    plan = build_answer_plan("What does 112:1-4 say?")

    assert plan.quran_plan is not None
    assert plan.tafsir_plan is None
    assert plan.allow_composition is False
