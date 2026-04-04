from __future__ import annotations

from fastapi import Request

from services.answer_engine.composer import compose_explain_answer
from services.answer_engine.evidence_pack import EvidencePack, build_quran_evidence, build_tafsir_evidence
from services.answer_engine.plan_types import AnswerMode
from services.answer_engine.planner_lite import build_answer_plan
from services.ask_router.route_types import AskRouteType
from services.ask_workflows.explain_quran_reference import explain_quran_reference
from services.ask_workflows.verifier_support import is_verifier_match_usable, run_arabic_quran_quote_workflow
from services.tafsir.service import TafsirService


def explain_answer(
    *,
    query: str,
    request: Request | None = None,
    include_tafsir: bool | None = None,
    tafsir_source_id: str | None = "tafsir:ibn-kathir-en",
    tafsir_limit: int = 3,
    database_url: str | None = None,
    debug: bool = False,
) -> dict[str, object]:
    plan = build_answer_plan(
        query,
        request=request,
        include_tafsir=include_tafsir,
        tafsir_source_id=tafsir_source_id,
        tafsir_limit=tafsir_limit,
        database_url=database_url,
        debug=debug,
    )

    evidence = EvidencePack(
        query=query,
        route_type=plan.route_type,
        action_type=plan.action_type,
    )

    if plan.mode == AnswerMode.ABSTAIN:
        if plan.abstain_reason:
            evidence.errors.append(plan.abstain_reason)
        return compose_explain_answer(plan, evidence)

    if plan.route_type == AskRouteType.EXPLICIT_QURAN_REFERENCE.value:
        explain_query = plan.route.get("reference_text") or query
        quran_result = explain_quran_reference(explain_query)
        evidence.resolution = quran_result.get("resolution")
        evidence.quran = build_quran_evidence(quran_result.get("quran_span"))
        if not quran_result.get("ok"):
            evidence.errors.append(quran_result.get("error") or "could_not_resolve_reference")
            return compose_explain_answer(plan, evidence)

        if plan.tafsir_plan is not None and evidence.quran is not None:
            selected_source_id = str(plan.tafsir_plan.params.get("source_id"))
            try:
                tafsir_service = TafsirService(database_url=database_url)
                hits = tafsir_service.get_overlap_for_quran_span(
                    source_id=selected_source_id,
                    surah_no=evidence.quran.surah_no,
                    ayah_start=evidence.quran.ayah_start,
                    ayah_end=evidence.quran.ayah_end,
                    limit=int(plan.tafsir_plan.params.get("limit", tafsir_limit)),
                )
                evidence.tafsir = build_tafsir_evidence(hits)
                if not evidence.tafsir:
                    evidence.warnings.append(
                        f"No approved Tafsir sections were found for {selected_source_id}; returned Quran-only answer."
                    )
            except (PermissionError, LookupError, RuntimeError, ValueError) as exc:
                evidence.warnings.append(f"Tafsir retrieval failed; returned Quran-only answer. Cause: {exc}")

        return compose_explain_answer(plan, evidence)

    if plan.route_type == AskRouteType.ARABIC_QURAN_QUOTE.value:
        quote_payload = plan.route.get("quote_payload") or query
        verifier = run_arabic_quran_quote_workflow(
            query,
            quote_payload=quote_payload,
            action_type=plan.action_type,
            request=request,
            debug=debug,
        )
        evidence.verifier_result = verifier.get("verifier_result")
        evidence.quote_payload = verifier.get("quote_payload")
        evidence.quran = build_quran_evidence(verifier.get("quran_span"))
        if verifier.get("error"):
            evidence.errors.append(verifier["error"])
        elif not is_verifier_match_usable(verifier.get("verifier_result") or {}):
            evidence.errors.append("no_usable_evidence")
        return compose_explain_answer(plan, evidence)

    evidence.errors.append("unsupported_query_type_for_now")
    return compose_explain_answer(plan, evidence)
