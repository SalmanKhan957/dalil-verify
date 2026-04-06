from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import Request

from domains.answer_engine.evidence_pack import HadithEvidence, QuranEvidence, TafsirEvidence, build_hadith_evidence, build_quran_evidence, build_tafsir_evidence
from domains.ask.planner_types import AskPlan, ResponseMode
from domains.ask.workflows.verifier_support import is_verifier_match_usable, run_arabic_quran_quote_workflow
from domains.hadith.retrieval.citation_lookup import HadithCitationLookupService
from domains.quran.repositories.context import resolve_quran_repository_context
from domains.quran.retrieval.fetcher import fetch_quran_span
from domains.tafsir.service import TafsirService


@dataclass(slots=True)
class QuranInvocationEvidence:
    quran: QuranEvidence | None = None
    resolution: dict[str, Any] | None = None
    verifier_result: dict[str, Any] | None = None
    quote_payload: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TafsirInvocationEvidence:
    tafsir: list[TafsirEvidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HadithInvocationEvidence:
    hadith: HadithEvidence | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def invoke_quran_domain(plan: AskPlan, *, request: Request | None = None, database_url: str | None = None) -> QuranInvocationEvidence:
    quran_plan_params = dict((plan.quran_plan.params if plan.quran_plan is not None else {}) or {})
    if plan.quran_plan is None and not plan.requires_quran_reference_resolution and not plan.requires_quran_verification:
        return QuranInvocationEvidence()
    repository_context = resolve_quran_repository_context(
        repository_mode=quran_plan_params.get("repository_mode"),
        database_url=quran_plan_params.get("database_url") or database_url,
        quran_work_source_id=quran_plan_params.get("quran_work_source_id"),
        translation_work_source_id=quran_plan_params.get("translation_work_source_id"),
    )

    if plan.requires_quran_reference_resolution:
        resolution = plan.resolved_quran_ref or {}
        if not resolution.get("resolved"):
            return QuranInvocationEvidence(resolution=resolution, errors=[str((resolution or {}).get("error") or "no_resolved_reference")])

        try:
            quran_span = fetch_quran_span(
                surah_no=int(resolution["surah_no"]),
                ayah_start=int(resolution["ayah_start"]),
                ayah_end=int(resolution["ayah_end"]),
                repository_mode=repository_context.repository_mode,
                database_url=repository_context.database_url,
                quran_work_source_id=repository_context.quran_work_source_id,
                translation_work_source_id=repository_context.translation_work_source_id,
            )
        except Exception as exc:  # pragma: no cover
            return QuranInvocationEvidence(resolution=resolution, errors=[f"quran_span_fetch_failed: {exc}"])

        return QuranInvocationEvidence(quran=build_quran_evidence(quran_span), resolution=resolution)

    if plan.requires_quran_verification:
        quote_payload = str(plan.route.get("quote_payload") or plan.query)
        verifier = run_arabic_quran_quote_workflow(
            plan.query,
            quote_payload=quote_payload,
            action_type=plan.action_type,
            request=request,
            debug=plan.debug,
            repository_mode=repository_context.repository_mode,
            database_url=repository_context.database_url,
            quran_work_source_id=repository_context.quran_work_source_id,
            translation_work_source_id=repository_context.translation_work_source_id,
        )
        evidence = QuranInvocationEvidence(
            resolution=plan.resolved_quran_ref,
            verifier_result=verifier.get("verifier_result"),
            quote_payload=verifier.get("quote_payload") or quote_payload,
        )
        if verifier.get("quran_span") is not None:
            evidence.quran = build_quran_evidence(verifier.get("quran_span"))
        if verifier.get("error"):
            evidence.errors.append(str(verifier["error"]))
        elif not is_verifier_match_usable(verifier.get("verifier_result") or {}):
            if plan.response_mode == ResponseMode.VERIFICATION_ONLY:
                evidence.warnings.append("verification_result_not_usable_for_quran_span")
            else:
                evidence.errors.append("insufficient_evidence")
        return evidence

    return QuranInvocationEvidence()


def invoke_tafsir_domain(plan: AskPlan, quran: QuranEvidence | None, *, database_url: str | None = None) -> TafsirInvocationEvidence:
    if not plan.use_tafsir or plan.tafsir_plan is None or quran is None:
        return TafsirInvocationEvidence()

    selected_source_id = str(plan.tafsir_plan.params.get("source_id") or plan.tafsir_plan.source_id or "")
    limit = int(plan.tafsir_plan.params.get("limit", 3))
    try:
        tafsir_service = TafsirService(database_url=database_url)
        hits = tafsir_service.get_overlap_for_quran_span(
            source_id=selected_source_id,
            surah_no=quran.surah_no,
            ayah_start=quran.ayah_start,
            ayah_end=quran.ayah_end,
            limit=limit,
        )
    except (PermissionError, LookupError, RuntimeError, ValueError) as exc:
        return TafsirInvocationEvidence(warnings=[f"Tafsir retrieval failed; returned Quran-only answer. Cause: {exc}"])

    tafsir = build_tafsir_evidence(hits)
    if not tafsir:
        return TafsirInvocationEvidence(tafsir=[], warnings=[f"No approved Tafsir sections were found for {selected_source_id}; returned Quran-only answer."])
    return TafsirInvocationEvidence(tafsir=tafsir)


def invoke_hadith_domain(plan: AskPlan, *, database_url: str | None = None) -> HadithInvocationEvidence:
    if plan.hadith_plan is None or plan.resolved_hadith_citation is None:
        return HadithInvocationEvidence()
    try:
        lookup = HadithCitationLookupService(database_url=database_url).lookup(plan.resolved_hadith_citation)
    except Exception as exc:  # pragma: no cover
        return HadithInvocationEvidence(errors=[f'hadith_lookup_failed: {exc}'])
    if not lookup.resolved or lookup.entry is None:
        return HadithInvocationEvidence(warnings=list(lookup.warnings), errors=[lookup.error or 'hadith_citation_not_found'])
    return HadithInvocationEvidence(
        hadith=build_hadith_evidence(lookup.entry, citation=lookup.citation),
        warnings=list(lookup.warnings),
        errors=[],
    )
