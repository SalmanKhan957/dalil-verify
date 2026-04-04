from __future__ import annotations

from typing import Any

from services.answer_engine.citation_renderer import render_citation_list
from services.answer_engine.contracts import make_explain_answer_payload
from services.answer_engine.evidence_pack import EvidencePack
from services.answer_engine.excerpting import build_tafsir_excerpt
from services.answer_engine.plan_types import AnswerMode, AnswerPlan


def _build_quran_support(evidence: EvidencePack) -> dict[str, Any] | None:
    if evidence.quran is None:
        return None

    quran = evidence.quran
    return {
        "citation_string": quran.citation_string,
        "surah_no": quran.surah_no,
        "ayah_start": quran.ayah_start,
        "ayah_end": quran.ayah_end,
        "surah_name_en": quran.surah_name_en,
        "surah_name_ar": quran.surah_name_ar,
        "arabic_text": quran.arabic_text,
        "translation_text": quran.translation_text,
        "canonical_source_id": quran.canonical_source_id,
        "translation_source_id": quran.translation_source_id,
    }


def _build_tafsir_support(evidence: EvidencePack) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tafsir in evidence.tafsir:
        hit = tafsir.hit
        excerpt, trimmed = build_tafsir_excerpt(hit.text_plain)
        items.append(
            {
                "source_id": hit.source_id,
                "canonical_section_id": hit.canonical_section_id,
                "display_text": f"{hit.citation_label} on Quran {hit.quran_span_ref}",
                "excerpt": excerpt,
                "text_html": hit.text_html,
                "surah_no": hit.surah_no,
                "ayah_start": hit.ayah_start,
                "ayah_end": hit.ayah_end,
                "coverage_mode": hit.coverage_mode,
                "coverage_confidence": float(hit.coverage_confidence),
                "anchor_verse_key": hit.anchor_verse_key,
                "quran_span_ref": hit.quran_span_ref,
                "excerpt_was_trimmed": trimmed,
            }
        )
    return items


def _condense_translation(translation_text: str, *, limit: int = 220) -> str:
    text = " ".join((translation_text or "").split()).strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text

    cut = text[:limit]
    for delimiter in (". ", "; ", ", "):
        idx = cut.rfind(delimiter)
        if idx >= int(limit * 0.55):
            return cut[: idx + 1].strip()
    space_idx = cut.rfind(" ")
    if space_idx >= int(limit * 0.55):
        cut = cut[:space_idx]
    return cut.rstrip(" ,;:-") + "…"


def _build_explanatory_answer_from_tafsir(plan: AnswerPlan, evidence: EvidencePack) -> str | None:
    quran = evidence.quran
    if quran is None or not evidence.tafsir:
        return None

    first_tafsir = evidence.tafsir[0].hit
    excerpt, _ = build_tafsir_excerpt(first_tafsir.text_plain, target_chars=420)
    if plan.mode == AnswerMode.FETCH_TEXT:
        return f"{quran.citation_string}: {_condense_translation(quran.translation_text or '', limit=260)}".strip()

    intro = f"In {first_tafsir.citation_label}, {quran.citation_string} is explained as follows:"
    if plan.mode in {AnswerMode.EXPLAIN, AnswerMode.VERIFY_THEN_EXPLAIN}:
        return f"{intro} {excerpt}".strip()
    if plan.mode == AnswerMode.VERIFY:
        return f"This matches {quran.citation_string}. {first_tafsir.citation_label} explains it as follows: {excerpt}".strip()
    return None


def _build_quran_only_answer(plan: AnswerPlan, evidence: EvidencePack) -> str | None:
    quran = evidence.quran
    if quran is None and evidence.verifier_result is not None:
        match_status = evidence.verifier_result.get("match_status") or "Verification result unavailable."
        return str(match_status)

    if quran is None:
        return None

    translation_text = _condense_translation(quran.translation_text or "")
    if plan.mode == AnswerMode.FETCH_TEXT:
        return f"{quran.citation_string}: {translation_text}".strip()

    if plan.mode in {AnswerMode.EXPLAIN, AnswerMode.VERIFY_THEN_EXPLAIN}:
        return f"{quran.citation_string} says: {translation_text}".strip()

    if plan.mode == AnswerMode.VERIFY:
        return f"This matches {quran.citation_string}.".strip()

    return None


def _build_answer_text(plan: AnswerPlan, evidence: EvidencePack) -> str | None:
    if plan.mode == AnswerMode.ABSTAIN:
        return None

    tafsir_answer = _build_explanatory_answer_from_tafsir(plan, evidence)
    if tafsir_answer:
        return tafsir_answer
    return _build_quran_only_answer(plan, evidence)


def _build_debug(plan: AnswerPlan, evidence: EvidencePack) -> dict[str, Any] | None:
    if not plan.debug:
        return None
    return {
        "plan": {
            "mode": plan.mode.value if hasattr(plan.mode, 'value') else str(plan.mode),
            "route_type": plan.route_type,
            "action_type": plan.action_type,
            "allow_composition": plan.allow_composition,
            "tafsir_requested": plan.tafsir_requested,
            "tafsir_explicit": plan.tafsir_explicit,
            "abstain_reason": plan.abstain_reason,
        },
        "route": plan.route,
        "resolution": evidence.resolution,
        "verifier_result": evidence.verifier_result,
        "warnings": evidence.warnings,
        "errors": evidence.errors,
        "raw_quran": evidence.quran.raw if evidence.quran else None,
        "raw_tafsir": [
            {
                "canonical_section_id": item.hit.canonical_section_id,
                "text_plain": item.hit.text_plain,
                "coverage_mode": item.hit.coverage_mode,
                "coverage_confidence": item.hit.coverage_confidence,
            }
            for item in evidence.tafsir
        ],
    }


def _derive_partial_success(plan: AnswerPlan, evidence: EvidencePack) -> bool:
    if evidence.quran is None:
        return False
    if plan.tafsir_requested and not evidence.tafsir and bool(evidence.warnings or evidence.errors):
        return True
    return False


def compose_explain_answer(plan: AnswerPlan, evidence: EvidencePack) -> dict[str, Any]:
    citations = render_citation_list(evidence)
    quran_support = _build_quran_support(evidence)
    tafsir_support = _build_tafsir_support(evidence)
    answer_text = _build_answer_text(plan, evidence)
    partial_success = _derive_partial_success(plan, evidence)

    error = None
    if plan.abstain_reason and not quran_support:
        error = plan.abstain_reason
    elif evidence.quran is None and evidence.errors:
        error = evidence.errors[0]

    warnings = list(evidence.warnings)

    return make_explain_answer_payload(
        ok=bool(answer_text or quran_support or tafsir_support) and not bool(plan.abstain_reason and not quran_support),
        query=plan.query,
        answer_mode=plan.mode.value if hasattr(plan.mode, "value") else str(plan.mode),
        route_type=plan.route_type,
        action_type=plan.action_type,
        answer_text=answer_text,
        citations=citations,
        quran_support=quran_support,
        tafsir_support=tafsir_support,
        resolution=evidence.resolution,
        partial_success=partial_success,
        warnings=warnings,
        debug=_build_debug(plan, evidence),
        error=error,
    )
