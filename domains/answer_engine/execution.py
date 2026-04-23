from __future__ import annotations

from fastapi import Request

from domains.answer_engine.domain_invocation import invoke_hadith_domain, invoke_quran_domain, invoke_tafsir_domain
from domains.answer_engine.evidence_pack import EvidencePack
from domains.ask.planner_types import AskPlan


def execute_plan(plan: AskPlan, *, request: Request | None = None, database_url: str | None = None) -> EvidencePack:
    evidence = EvidencePack(
        query=plan.query,
        route_type=plan.route_type,
        action_type=plan.action_type,
        selected_domains=[domain.value if hasattr(domain, "value") else str(domain) for domain in plan.selected_domains],
        response_mode=plan.response_mode.value if hasattr(plan.response_mode, "value") else str(plan.response_mode),
    )

    if plan.should_abstain:
        effective_database_url = database_url or plan.database_url
        if plan.debug and plan.hadith_plan is not None and bool(plan.hadith_plan.params.get('shadow_only')):
            hadith_evidence = invoke_hadith_domain(plan, database_url=effective_database_url)
            if hadith_evidence.diagnostics:
                evidence.diagnostics['hadith'] = hadith_evidence.diagnostics
        if plan.abstain_reason is not None:
            evidence.errors.append(plan.abstain_reason.value)
        return evidence

    effective_database_url = database_url
    if effective_database_url is None and plan.quran_plan is not None:
        effective_database_url = plan.quran_plan.params.get("database_url")
    if effective_database_url is None:
        effective_database_url = plan.database_url

    if plan.quran_plan is not None or plan.requires_quran_reference_resolution or plan.requires_quran_verification:
        quran_evidence = invoke_quran_domain(plan, request=request, database_url=effective_database_url)
        evidence.quran = quran_evidence.quran
        evidence.resolution = quran_evidence.resolution
        evidence.verifier_result = quran_evidence.verifier_result
        evidence.quote_payload = quran_evidence.quote_payload
        evidence.warnings.extend(quran_evidence.warnings)
        evidence.errors.extend(quran_evidence.errors)

    tafsir_evidence = invoke_tafsir_domain(plan, evidence.quran, database_url=effective_database_url)
    evidence.tafsir = tafsir_evidence.tafsir
    evidence.warnings.extend(tafsir_evidence.warnings)
    evidence.errors.extend(tafsir_evidence.errors)

    hadith_evidence = invoke_hadith_domain(plan, database_url=effective_database_url)
    evidence.hadith = hadith_evidence.hadith
    evidence.supporting_hadiths = list(hadith_evidence.supporting_hadiths or [])
    evidence.warnings.extend(hadith_evidence.warnings)
    evidence.errors.extend(hadith_evidence.errors)
    if hadith_evidence.diagnostics:
        evidence.diagnostics['hadith'] = hadith_evidence.diagnostics
    return evidence
