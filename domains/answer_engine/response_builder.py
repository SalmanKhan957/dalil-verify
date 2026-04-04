from __future__ import annotations

from typing import Any

from domains.answer_engine.citation_renderer import render_citation_list
from domains.answer_engine.contracts import make_explain_answer_payload
from domains.answer_engine.evidence_pack import EvidencePack
from domains.answer_engine.excerpting import build_tafsir_excerpt
from domains.ask.planner_types import AskPlan, ResponseMode



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



def _build_quran_with_tafsir_answer(plan: AskPlan, evidence: EvidencePack) -> str | None:
    quran = evidence.quran
    if quran is None or not evidence.tafsir:
        return None

    first_tafsir = evidence.tafsir[0].hit
    excerpt, _ = build_tafsir_excerpt(first_tafsir.text_plain, target_chars=420)
    return f"In {first_tafsir.citation_label}, {quran.citation_string} is explained as follows: {excerpt}".strip()



def _build_quran_only_answer(plan: AskPlan, evidence: EvidencePack) -> str | None:
    quran = evidence.quran
    if quran is None and evidence.verifier_result is not None:
        match_status = evidence.verifier_result.get("match_status") or "Verification result unavailable."
        return str(match_status)
    if quran is None:
        return None

    translation_text = _condense_translation(quran.translation_text or "")
    if plan.response_mode == ResponseMode.QURAN_TEXT:
        return f"{quran.citation_string}: {translation_text}".strip()
    if plan.response_mode in {ResponseMode.QURAN_EXPLANATION, ResponseMode.VERIFICATION_THEN_EXPLAIN}:
        return f"{quran.citation_string} says: {translation_text}".strip()
    if plan.response_mode == ResponseMode.VERIFICATION_ONLY:
        return f"This matches {quran.citation_string}.".strip()
    if plan.response_mode == ResponseMode.QURAN_WITH_TAFSIR:
        return f"{quran.citation_string} says: {translation_text}".strip()
    return None



def _build_answer_text(plan: AskPlan, evidence: EvidencePack) -> str | None:
    if plan.response_mode == ResponseMode.ABSTAIN:
        return None
    if plan.response_mode == ResponseMode.QURAN_WITH_TAFSIR:
        tafsir_answer = _build_quran_with_tafsir_answer(plan, evidence)
        if tafsir_answer:
            return tafsir_answer
    return _build_quran_only_answer(plan, evidence)



def _build_debug(plan: AskPlan, evidence: EvidencePack) -> dict[str, Any] | None:
    if not plan.debug:
        return None
    return {
        "plan": {
            "response_mode": plan.response_mode.value if hasattr(plan.response_mode, "value") else str(plan.response_mode),
            "route_type": plan.route_type,
            "action_type": plan.action_type,
            "eligible_domains": [d.value if hasattr(d, "value") else str(d) for d in plan.eligible_domains],
            "selected_domains": [d.value if hasattr(d, "value") else str(d) for d in plan.selected_domains],
            "requires_quran_verification": plan.requires_quran_verification,
            "requires_quran_reference_resolution": plan.requires_quran_reference_resolution,
            "use_tafsir": plan.use_tafsir,
            "evidence_requirements": [e.value if hasattr(e, "value") else str(e) for e in plan.evidence_requirements],
            "should_abstain": plan.should_abstain,
            "abstain_reason": plan.abstain_reason.value if plan.abstain_reason else None,
            "tafsir_requested": plan.tafsir_requested,
            "tafsir_explicit": plan.tafsir_explicit,
            "notes": list(plan.notes),
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



def _derive_partial_success(plan: AskPlan, evidence: EvidencePack) -> bool:
    if evidence.quran is None:
        return False
    if plan.use_tafsir and not evidence.tafsir and bool(evidence.warnings or evidence.errors):
        return True
    return False



def build_explain_answer_payload(plan: AskPlan, evidence: EvidencePack) -> dict[str, Any]:
    citations = render_citation_list(evidence)
    quran_support = _build_quran_support(evidence)
    tafsir_support = _build_tafsir_support(evidence)
    answer_text = _build_answer_text(plan, evidence)
    partial_success = _derive_partial_success(plan, evidence)

    error = None
    if plan.should_abstain and not quran_support:
        error = plan.abstain_reason.value if plan.abstain_reason else None
    elif evidence.quran is None and evidence.errors:
        error = evidence.errors[0]

    payload = make_explain_answer_payload(
        ok=bool(answer_text or quran_support or tafsir_support) and not bool(plan.should_abstain and not quran_support),
        query=plan.query,
        answer_mode=plan.response_mode.value if hasattr(plan.response_mode, "value") else str(plan.response_mode),
        route_type=plan.route_type,
        action_type=plan.action_type,
        answer_text=answer_text,
        citations=citations,
        quran_support=quran_support,
        tafsir_support=tafsir_support,
        resolution=evidence.resolution,
        partial_success=partial_success,
        warnings=list(evidence.warnings),
        debug=_build_debug(plan, evidence),
        error=error,
    )
    payload["quran_span"] = evidence.quran.raw if evidence.quran else None
    payload["verifier_result"] = evidence.verifier_result
    payload["quote_payload"] = evidence.quote_payload
    return payload
