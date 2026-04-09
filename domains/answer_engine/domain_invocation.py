from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import Request

from domains.answer_engine.evidence_pack import HadithEvidence, QuranEvidence, TafsirEvidence, build_hadith_evidence, build_quran_evidence, build_tafsir_evidence
from domains.ask.planner_types import AskPlan, ResponseMode
from domains.ask.workflows.verifier_support import is_verifier_match_usable, run_arabic_quran_quote_workflow
from domains.quran.repositories.context import resolve_quran_repository_context
from domains.quran.retrieval.fetcher import fetch_quran_span


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
    diagnostics: dict[str, Any] = field(default_factory=dict)


def _block_legacy_topical_fallback(diagnostics: dict[str, Any]) -> bool:
    shadow = dict(diagnostics.get('topical_v2_shadow') or {})
    debug = dict(shadow.get('debug') or {})
    family_decision = dict(debug.get('family_decision') or {})
    if family_decision.get('allow_generic_fallback') is False:
        return True
    return str(debug.get('retrieval_family') or '') in {'entity_eschatology', 'narrative_event', 'ritual_practice'}


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
    if plan.tafsir_plan is None:
        return TafsirInvocationEvidence()

    selected_source_id = str(plan.tafsir_plan.params.get("source_id") or plan.tafsir_plan.source_id or "")
    limit = int(plan.tafsir_plan.params.get("limit", 3))
    retrieval_mode = str(plan.tafsir_plan.params.get('retrieval_mode') or 'overlap')
    try:
        from domains.tafsir.service import TafsirService
        tafsir_service = TafsirService(database_url=database_url)
        if retrieval_mode == 'lexical':
            topic_query = str(plan.tafsir_plan.params.get('query_text') or plan.topical_query or plan.query)
            minimum_score = float(plan.tafsir_plan.params.get('minimum_score', 0.0) or 0.0)
            hits = tafsir_service.search_topically(
                query_text=topic_query,
                source_id=selected_source_id,
                limit=limit,
            )
            if hits:
                top_score = float(getattr(hits[0], 'score', 0.0) or 0.0)
                if top_score < minimum_score:
                    return TafsirInvocationEvidence(tafsir=[], warnings=[f"No Tafsir topical match met the minimum evidence threshold for {selected_source_id}."], errors=['insufficient_evidence'])
            tafsir = build_tafsir_evidence(hits)
            if not tafsir:
                return TafsirInvocationEvidence(tafsir=[], warnings=[f"No approved Tafsir topical matches were found for {selected_source_id}."], errors=['insufficient_evidence'])
            return TafsirInvocationEvidence(tafsir=tafsir)

        if not plan.use_tafsir or quran is None:
            return TafsirInvocationEvidence()
        hits = tafsir_service.get_overlap_for_quran_span(
            source_id=selected_source_id,
            surah_no=quran.surah_no,
            ayah_start=quran.ayah_start,
            ayah_end=quran.ayah_end,
            limit=limit,
        )
    except (PermissionError, LookupError, RuntimeError, ValueError) as exc:
        return TafsirInvocationEvidence(warnings=[f"Tafsir retrieval failed; returned non-Tafsir answer path. Cause: {exc}"])

    tafsir = build_tafsir_evidence(hits)
    if not tafsir:
        return TafsirInvocationEvidence(tafsir=[], warnings=[f"No approved Tafsir sections were found for {selected_source_id}; returned without Tafsir support."])
    return TafsirInvocationEvidence(tafsir=tafsir)


def invoke_hadith_domain(plan: AskPlan, *, database_url: str | None = None) -> HadithInvocationEvidence:
    if plan.hadith_plan is None:
        return HadithInvocationEvidence()

    retrieval_mode = str(plan.hadith_plan.params.get('retrieval_mode') or 'citation')
    if retrieval_mode in {'lexical', 'topical_v2_shadow'}:
        try:
            from domains.hadith.service import HadithService
            query_text = str(plan.hadith_plan.params.get('query_text') or plan.topical_query or plan.query)
            limit = int(plan.hadith_plan.params.get('limit', 5))
            baseline_hits = HadithService(database_url=database_url).search_topically(
                query_text=query_text,
                collection_source_id=plan.hadith_plan.params.get('source_id') or plan.hadith_plan.source_id,
                limit=limit,
            )
            minimum_score = float(plan.hadith_plan.params.get('minimum_score', 0.0) or 0.0)
        except Exception as exc:  # pragma: no cover
            return HadithInvocationEvidence(errors=[f'hadith_topical_lookup_failed: {exc}'])
        if not baseline_hits:
            return HadithInvocationEvidence(warnings=['no_hadith_topical_matches'], errors=['insufficient_evidence'])
        top = baseline_hits[0]
        top_score = float(getattr(top, 'score', 0.0) or 0.0)
        diagnostics: dict[str, Any] = {}
        selected_hadith = None
        selected_warnings: list[str] = []
        authority_source = 'legacy_lexical'
        if retrieval_mode == 'topical_v2_shadow':
            try:
                from domains.hadith_topical.hydrator import hydrate_hadith_entries_by_collection_refs
                from domains.hadith_topical.search_service import HadithTopicalSearchService
                shadow_result = HadithTopicalSearchService(database_url=database_url).search(
                    raw_query=query_text,
                    collection_source_id=plan.hadith_plan.params.get('source_id') or plan.hadith_plan.source_id,
                    limit=limit,
                    lexical_hits=list(baseline_hits),
                )
                diagnostics['topical_v2_shadow'] = {
                    'abstain': shadow_result.abstain,
                    'abstain_reason': shadow_result.abstain_reason,
                    'warnings': list(shadow_result.warnings),
                    'selected_refs': [candidate.canonical_ref for candidate in shadow_result.selected],
                    'debug': shadow_result.debug,
                }
                if not shadow_result.abstain and shadow_result.selected:
                    selected_candidate = shadow_result.selected[0]
                    hydrated = hydrate_hadith_entries_by_collection_refs(
                        [selected_candidate.canonical_ref],
                        collection_source_id=plan.hadith_plan.params.get('source_id') or plan.hadith_plan.source_id,
                        database_url=database_url,
                    )
                    selected_entry = hydrated.get(selected_candidate.canonical_ref)
                    if selected_entry is not None:
                        selected_hadith = build_hadith_evidence(
                            selected_entry,
                            snippet=(getattr(selected_candidate, 'metadata', {}) or {}).get('snippet'),
                            retrieval_method='topical_v2',
                            matched_terms=tuple(getattr(selected_candidate, 'matched_terms', ()) or ()),
                            authority_source='topical_v2',
                            retrieval_origin=getattr(selected_candidate, 'retrieval_origin', None),
                            matched_topics=tuple(getattr(selected_candidate, 'matched_topics', ()) or ()),
                            central_topic_score=getattr(selected_candidate, 'central_topic_score', None),
                            answerability_score=getattr(selected_candidate, 'answerability_score', None),
                            guidance_role=getattr(selected_candidate, 'guidance_role', None),
                            topic_family=getattr(selected_candidate, 'topic_family', None),
                            fusion_score=getattr(selected_candidate, 'fusion_score', None),
                            rerank_score=getattr(selected_candidate, 'rerank_score', None),
                            lexical_score=getattr(selected_candidate, 'lexical_score', None),
                            vector_score=getattr(selected_candidate, 'vector_score', None),
                        )
                        selected_hadith.raw.update({
                            'supporting_refs': list((shadow_result.debug.get('evidence_bundle') or {}).get('supporting_refs') or []),
                            'evidence_bundle_size': int((shadow_result.debug.get('evidence_bundle') or {}).get('candidate_count') or 0),
                            'llm_composition_ready': bool(shadow_result.debug.get('llm_composition_contract')),
                            'guidance_unit_id': ((getattr(selected_candidate, 'metadata', {}) or {}).get('guidance_unit_id')),
                            'guidance_summary': ((getattr(selected_candidate, 'metadata', {}) or {}).get('contextual_summary')),
                            'source_excerpt': ((getattr(selected_candidate, 'metadata', {}) or {}).get('span_text')),
                        })
                        authority_source = 'topical_v2'
                        selected_warnings = list(shadow_result.warnings)
            except Exception as exc:  # pragma: no cover
                diagnostics['topical_v2_shadow'] = {'error': str(exc)}
        if selected_hadith is not None:
            return HadithInvocationEvidence(
                hadith=selected_hadith,
                warnings=selected_warnings,
                errors=[],
                diagnostics=diagnostics,
            )
        if top_score < minimum_score:
            return HadithInvocationEvidence(
                warnings=[f"No Hadith topical match met the minimum evidence threshold for {plan.hadith_plan.params.get('source_id') or plan.hadith_plan.source_id}."],
                errors=['insufficient_evidence'],
                diagnostics=diagnostics,
            )
        if retrieval_mode == 'topical_v2_shadow':
            shadow_diag = diagnostics.get('topical_v2_shadow') or {}
            if _block_legacy_topical_fallback(diagnostics) and not shadow_diag.get('selected_refs'):
                warnings = list(dict.fromkeys(list(shadow_diag.get('warnings') or ()) + ['no_family_safe_topical_match']))
                return HadithInvocationEvidence(
                    warnings=warnings,
                    errors=['insufficient_evidence'],
                    diagnostics=diagnostics,
                )
            if top_score < minimum_score and not shadow_diag.get('selected_refs'):
                return HadithInvocationEvidence(
                    warnings=['no_ranked_candidate_passed_thresholds'],
                    errors=['insufficient_evidence'],
                    diagnostics=diagnostics,
                )
        fallback_hadith = build_hadith_evidence(
            top.entry,
            snippet=top.snippet,
            retrieval_method=top.retrieval_method,
            matched_terms=top.matched_terms,
            authority_source=authority_source,
            retrieval_origin=getattr(top, 'retrieval_method', None),
        )
        if fallback_hadith is not None:
            fallback_hadith.raw.update({
                'supporting_refs': [hit.entry.canonical_ref_collection for hit in list(baseline_hits)[: min(len(baseline_hits), 5)]],
                'evidence_bundle_size': min(len(baseline_hits), 5),
                'llm_composition_ready': False,
            })
        return HadithInvocationEvidence(
            hadith=fallback_hadith,
            warnings=(['additional_hadith_matches_available'] if len(baseline_hits) > 1 else []),
            errors=[],
            diagnostics=diagnostics,
        )

    if plan.resolved_hadith_citation is None:
        return HadithInvocationEvidence()
    try:
        from domains.hadith.retrieval.citation_lookup import HadithCitationLookupService
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
