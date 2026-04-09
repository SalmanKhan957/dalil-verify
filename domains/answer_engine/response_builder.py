from __future__ import annotations

from typing import Any

from domains.answer_engine.citation_renderer import render_citation_list
from domains.answer_engine.contracts import make_explain_answer_payload
from domains.answer_engine.evidence_pack import EvidencePack
from domains.answer_engine.excerpting import build_tafsir_excerpt
from domains.answer_engine.orchestration_contract import build_orchestration_envelope, serialize_contract
from domains.ask.planner_types import AskPlan, ResponseMode


def _clean_hadith_book_title(value: Any, *, language: str) -> str | None:
    text = ' '.join(str(value or '').split()).strip()
    if not text:
        return None
    if language == 'en':
        lower = text.lower()
        if lower in {'chapter', 'chapter:'}:
            return None
        if lower.startswith('chapter:'):
            stripped = text.split(':', 1)[1].strip()
            return stripped or None
        return text
    if language == 'ar':
        if text in {'باب', 'باب:'}:
            return None
        if text.startswith('باب'):
            stripped = text[3:].strip(' :،-ـ')
            return stripped or None
        return text
    return text


def _resolve_hadith_numbering_quality(evidence: EvidencePack) -> str:
    raw = dict((evidence.hadith.raw if evidence.hadith else {}) or {})
    raw_quality = str(raw.get('numbering_quality') or '').strip()
    if raw_quality:
        return raw_quality
    if raw.get('reference_url') and raw.get('public_collection_number') is not None:
        return 'reference_url_linked'
    if 'hadith_bootstrap_numbering_unverified' in (evidence.warnings or []):
        return 'bootstrap_unverified'
    return 'collection_number_stable'


def _surface_hadith_approval(hadith_policy: Any) -> bool:
    if hadith_policy is None:
        return False
    if bool(getattr(hadith_policy, 'approved_for_answering', False)):
        return True
    return bool(getattr(hadith_policy, 'allowed', False) and getattr(hadith_policy, 'included', False) and getattr(hadith_policy, 'selected_capability', None))


def _build_legacy_hadith_entry(evidence: EvidencePack) -> dict[str, Any] | None:
    if evidence.hadith is None:
        return None
    raw = dict(evidence.hadith.raw or {})
    raw['book_title_en'] = _clean_hadith_book_title(raw.get('book_title_en'), language='en')
    raw['book_title_ar'] = _clean_hadith_book_title(raw.get('book_title_ar'), language='ar')
    raw['numbering_quality'] = _resolve_hadith_numbering_quality(evidence)
    return raw


def _build_quran_support(plan: AskPlan, evidence: EvidencePack) -> dict[str, Any] | None:
    if evidence.quran is None:
        return None

    quran = evidence.quran
    return {
        'citation_string': quran.citation_string,
        'surah_no': quran.surah_no,
        'ayah_start': quran.ayah_start,
        'ayah_end': quran.ayah_end,
        'surah_name_en': quran.surah_name_en,
        'surah_name_ar': quran.surah_name_ar,
        'arabic_text': quran.arabic_text,
        'translation_text': quran.translation_text,
        'canonical_source_id': quran.canonical_source_id,
        'quran_source_id': plan.quran_work_source_id or quran.quran_source_id,
        'translation_source_id': plan.translation_work_source_id or quran.translation_source_id,
    }


def _build_hadith_support(evidence: EvidencePack) -> dict[str, Any] | None:
    if evidence.hadith is None:
        return None
    hadith = evidence.hadith
    numbering_quality = _resolve_hadith_numbering_quality(evidence)
    raw = dict(hadith.raw or {})
    return {
        'citation_string': hadith.citation_string,
        'canonical_ref': hadith.canonical_ref,
        'canonical_ref_book_hadith': raw.get('canonical_ref_book_hadith'),
        'canonical_ref_book_chapter_hadith': raw.get('canonical_ref_book_chapter_hadith'),
        'collection_source_id': hadith.collection_source_id,
        'collection_slug': hadith.collection_slug,
        'collection_hadith_number': hadith.collection_hadith_number,
        'book_number': hadith.book_number,
        'chapter_number': hadith.chapter_number,
        'in_book_hadith_number': hadith.in_book_hadith_number,
        'reference_url': raw.get('reference_url'),
        'in_book_reference_text': raw.get('in_book_reference_text'),
        'public_collection_number': raw.get('public_collection_number'),
        'book_title_en': _clean_hadith_book_title(raw.get('book_title_en'), language='en'),
        'book_title_ar': _clean_hadith_book_title(raw.get('book_title_ar'), language='ar'),
        'english_narrator': hadith.english_narrator,
        'english_text': hadith.english_text,
        'arabic_text': hadith.arabic_text,
        'grading_label': hadith.grading_label,
        'grading_text': hadith.grading_text,
        'snippet': hadith.snippet,
        'retrieval_method': hadith.retrieval_method,
        'matched_terms': list(hadith.matched_terms),
        'authority_source': raw.get('authority_source'),
        'retrieval_origin': raw.get('retrieval_origin'),
        'matched_topics': list(raw.get('matched_topics') or []),
        'central_topic_score': raw.get('central_topic_score'),
        'answerability_score': raw.get('answerability_score'),
        'guidance_role': raw.get('guidance_role'),
        'guidance_unit_id': raw.get('guidance_unit_id'),
        'guidance_summary': raw.get('guidance_summary'),
        'source_excerpt': raw.get('source_excerpt'),
        'topic_family': raw.get('topic_family'),
        'fusion_score': raw.get('fusion_score'),
        'rerank_score': raw.get('rerank_score'),
        'lexical_score': raw.get('lexical_score'),
        'vector_score': raw.get('vector_score'),
        'supporting_refs': list(raw.get('supporting_refs') or []),
        'evidence_bundle_size': raw.get('evidence_bundle_size'),
        'llm_composition_ready': bool(raw.get('llm_composition_ready')),
        'numbering_quality': numbering_quality,
    }


def _build_tafsir_support(evidence: EvidencePack) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tafsir in evidence.tafsir:
        hit = tafsir.hit
        prebuilt_snippet = getattr(hit, 'snippet', None)
        if prebuilt_snippet:
            excerpt = str(prebuilt_snippet)
            trimmed = False
        else:
            excerpt, trimmed = build_tafsir_excerpt(str(getattr(hit, 'text_plain', '') or ''))
        items.append(
            {
                'source_id': getattr(hit, 'source_id', None),
                'canonical_section_id': getattr(hit, 'canonical_section_id', None),
                'display_text': f"{getattr(hit, 'citation_label', 'Tafsir')} on Quran {getattr(hit, 'quran_span_ref', '')}",
                'excerpt': excerpt,
                'text_html': getattr(hit, 'text_html', None),
                'surah_no': getattr(hit, 'surah_no', None),
                'ayah_start': getattr(hit, 'ayah_start', None),
                'ayah_end': getattr(hit, 'ayah_end', None),
                'coverage_mode': getattr(hit, 'coverage_mode', 'lexical_topic_match'),
                'coverage_confidence': float(getattr(hit, 'coverage_confidence', getattr(hit, 'score', 0.0)) or 0.0),
                'anchor_verse_key': getattr(hit, 'anchor_verse_key', None),
                'quran_span_ref': getattr(hit, 'quran_span_ref', None),
                'excerpt_was_trimmed': trimmed,
                'matched_terms': list(getattr(hit, 'matched_terms', ()) or ()),
                'retrieval_method': getattr(hit, 'retrieval_method', None),
            }
        )
    return items


def _condense_translation(translation_text: str, *, limit: int = 220) -> str:
    text = ' '.join((translation_text or '').split()).strip()
    if not text:
        return ''
    if len(text) <= limit:
        return text

    cut = text[:limit]
    for delimiter in ('. ', '; ', ', '):
        idx = cut.rfind(delimiter)
        if idx >= int(limit * 0.55):
            return cut[: idx + 1].strip()
    space_idx = cut.rfind(' ')
    if space_idx >= int(limit * 0.55):
        cut = cut[:space_idx]
    return cut.rstrip(' ,;:-') + '…'


def _build_quran_with_tafsir_answer(plan: AskPlan, evidence: EvidencePack) -> str | None:
    del plan
    quran = evidence.quran
    if quran is None or not evidence.tafsir:
        return None

    first_tafsir = evidence.tafsir[0].hit
    translation_text = _condense_translation(quran.translation_text or '')
    if translation_text:
        return (
            f'{quran.citation_string} says: {translation_text} '
            f'Retrieved commentary from {getattr(first_tafsir, "citation_label", "Tafsir")} is attached below.'
        ).strip()
    return f'Retrieved commentary from {getattr(first_tafsir, "citation_label", "Tafsir")} on {quran.citation_string} is attached below.'.strip()


def _build_quran_only_answer(plan: AskPlan, evidence: EvidencePack) -> str | None:
    quran = evidence.quran
    if quran is None and evidence.verifier_result is not None:
        match_status = evidence.verifier_result.get('match_status') or 'Verification result unavailable.'
        return str(match_status)
    if quran is None:
        return None

    translation_text = _condense_translation(quran.translation_text or '')
    if plan.response_mode == ResponseMode.QURAN_TEXT:
        return f'{quran.citation_string}: {translation_text}'.strip()
    if plan.response_mode in {ResponseMode.QURAN_EXPLANATION, ResponseMode.VERIFICATION_THEN_EXPLAIN}:
        return f'{quran.citation_string} says: {translation_text}'.strip()
    if plan.response_mode == ResponseMode.VERIFICATION_ONLY:
        return f'This matches {quran.citation_string}.'.strip()
    if plan.response_mode == ResponseMode.QURAN_WITH_TAFSIR:
        return f'{quran.citation_string} says: {translation_text}'.strip()
    return None


def _build_hadith_answer(plan: AskPlan, evidence: EvidencePack) -> str | None:
    hadith = evidence.hadith
    if hadith is None:
        return None
    narrator = ' '.join((hadith.english_narrator or '').split()).strip()
    text = ' '.join((hadith.english_text or '').split()).strip()
    if plan.response_mode == ResponseMode.HADITH_TEXT:
        if narrator:
            return f'{hadith.citation_string}: {narrator} {text}'.strip()
        return f'{hadith.citation_string}: {text}'.strip()
    if plan.response_mode == ResponseMode.HADITH_EXPLANATION:
        if narrator and text:
            return (
                f'According to {hadith.citation_string}, {narrator} {text} '
                f'The retrieved narration is attached below as the grounding source.'
            ).strip()
        if text:
            return f'According to {hadith.citation_string}, {text} The retrieved narration is attached below as the grounding source.'.strip()
        return f'{hadith.citation_string} was retrieved, but the stored narration text is empty.'.strip()
    return None


def _build_topical_tafsir_answer(evidence: EvidencePack) -> str | None:
    if not evidence.tafsir:
        return None
    first = evidence.tafsir[0].hit
    return f"Retrieved relevant Tafsir support from {getattr(first, 'citation_label', 'Tafsir')} for this topic. The matched commentary sections are attached below."


def _build_topical_hadith_answer(evidence: EvidencePack) -> str | None:
    if evidence.hadith is None:
        return None
    return f"Retrieved a relevant narration from {evidence.hadith.citation_string} for this topic. The matched source text is attached below."




def _build_clarify_answer(plan: AskPlan) -> str | None:
    prompt = ' '.join((plan.clarify_prompt or '').split()).strip()
    if not prompt:
        return None
    return prompt

def _build_topical_multi_source_answer(evidence: EvidencePack) -> str | None:
    if evidence.tafsir and evidence.hadith is not None:
        first = evidence.tafsir[0].hit
        return f"Retrieved relevant Tafsir support from {getattr(first, 'citation_label', 'Tafsir')} and a relevant narration from {evidence.hadith.citation_string}. Both source-grounded supports are attached below."
    if evidence.tafsir:
        return _build_topical_tafsir_answer(evidence)
    if evidence.hadith is not None:
        return _build_topical_hadith_answer(evidence)
    return None


def _build_abstain_answer(plan: AskPlan) -> str | None:
    hadith_policy = plan.source_policy.hadith if plan.source_policy is not None else None
    policy_reason = str(hadith_policy.policy_reason or '').strip() if hadith_policy is not None else ''
    if plan.route_type == 'topical_hadith_query' and policy_reason == 'topical_hadith_temporarily_disabled':
        return 'Topical Hadith answers are temporarily disabled in this release. Direct Hadith references such as “Bukhari 20” are still supported.'
    if plan.route_type == 'topical_hadith_query' and policy_reason == 'hadith_mode_blocks_topical_retrieval':
        return 'Topical Hadith retrieval is disabled for this request because hadith.mode is set to explicit_lookup_only. Direct Hadith references are still supported.'
    return None


def _build_answer_text(plan: AskPlan, evidence: EvidencePack) -> str | None:
    if plan.response_mode == ResponseMode.ABSTAIN:
        return _build_abstain_answer(plan)
    if plan.response_mode == ResponseMode.CLARIFY:
        return _build_clarify_answer(plan)
    if plan.response_mode == ResponseMode.TOPICAL_TAFSIR:
        return _build_topical_tafsir_answer(evidence)
    if plan.response_mode == ResponseMode.TOPICAL_HADITH:
        return _build_topical_hadith_answer(evidence)
    if plan.response_mode == ResponseMode.TOPICAL_MULTI_SOURCE:
        return _build_topical_multi_source_answer(evidence)
    if plan.hadith_plan is not None and plan.route_type != 'topical_hadith_query' and plan.route_type != 'topical_multi_source_query':
        return _build_hadith_answer(plan, evidence)
    if plan.use_tafsir and evidence.tafsir:
        tafsir_answer = _build_quran_with_tafsir_answer(plan, evidence)
        if tafsir_answer:
            return tafsir_answer
    return _build_quran_only_answer(plan, evidence)


def _build_quran_source_selection(plan: AskPlan) -> dict[str, Any] | None:
    if not any(
        [
            plan.repository_mode,
            plan.quran_work_source_id,
            plan.translation_work_source_id,
            plan.requested_quran_work_source_id,
            plan.requested_translation_work_source_id,
        ]
    ):
        return None

    return {
        'repository_mode': plan.repository_mode,
        'source_resolution_strategy': plan.source_resolution_strategy,
        'requested_quran_text_source_id': plan.requested_quran_work_source_id,
        'requested_quran_translation_source_id': plan.requested_translation_work_source_id,
        'selected_quran_text_source_id': plan.quran_work_source_id,
        'selected_quran_translation_source_id': plan.translation_work_source_id,
    }


def _build_source_policy(plan: AskPlan) -> dict[str, Any] | None:
    if plan.source_policy is None:
        return None
    quran_policy = plan.source_policy.quran
    tafsir_policy = plan.source_policy.tafsir
    payload = {
        'quran': {
            'domain': quran_policy.domain,
            'allowed': quran_policy.allowed,
            'included': quran_policy.included,
            'policy_reason': quran_policy.policy_reason,
            'selected_capability': quran_policy.selected_capability,
            'available_capabilities': list(quran_policy.available_capabilities),
            'requested_text_source_id': quran_policy.requested_text_source_id,
            'requested_translation_source_id': quran_policy.requested_translation_source_id,
            'selected_text_source_id': quran_policy.selected_text_source_id,
            'selected_translation_source_id': quran_policy.selected_translation_source_id,
            'text_source_origin': quran_policy.text_source_origin,
            'translation_source_origin': quran_policy.translation_source_origin,
        },
        'tafsir': {
            'domain': tafsir_policy.domain,
            'selected_capability': tafsir_policy.selected_capability,
            'available_capabilities': list(tafsir_policy.available_capabilities),
            'requested': tafsir_policy.requested,
            'request_origin': tafsir_policy.request_origin,
            'requested_source_id': tafsir_policy.requested_source_id,
            'selected_source_id': tafsir_policy.selected_source_id,
            'request_mode': tafsir_policy.request_mode,
            'mode_enforced': tafsir_policy.mode_enforced,
            'allowed': tafsir_policy.allowed,
            'included': tafsir_policy.included,
            'policy_reason': tafsir_policy.policy_reason,
        },
    }
    hadith_policy = plan.source_policy.hadith
    if hadith_policy is not None:
        payload['hadith'] = {
            'domain': hadith_policy.domain,
            'selected_capability': hadith_policy.selected_capability,
            'available_capabilities': list(hadith_policy.available_capabilities),
            'requested': hadith_policy.requested,
            'request_origin': hadith_policy.request_origin,
            'requested_source_id': hadith_policy.requested_source_id,
            'selected_source_id': hadith_policy.selected_source_id,
            'request_mode': hadith_policy.request_mode,
            'mode_enforced': hadith_policy.mode_enforced,
            'allowed': hadith_policy.allowed,
            'included': hadith_policy.included,
            'approved_for_answering': _surface_hadith_approval(hadith_policy),
            'answer_capability': hadith_policy.answer_capability,
            'public_response_scope': hadith_policy.public_response_scope,
            'policy_reason': hadith_policy.policy_reason,
        }
    return payload


def _build_orchestration_payload(plan: AskPlan, evidence: EvidencePack, *, answer_text: str | None, tafsir_support: list[dict[str, Any]], source_policy: dict[str, Any] | None, partial_success: bool) -> dict[str, Any]:
    return serialize_contract(
        build_orchestration_envelope(
            plan=plan,
            evidence=evidence,
            answer_text=answer_text,
            tafsir_support=tafsir_support,
            source_policy=source_policy,
            partial_success=partial_success,
        )
    )


def _build_debug(plan: AskPlan, evidence: EvidencePack, *, source_policy: dict[str, Any] | None, orchestration: dict[str, Any], conversation: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not plan.debug:
        return None
    return {
        'plan': {
            'response_mode': plan.response_mode.value if hasattr(plan.response_mode, 'value') else str(plan.response_mode),
            'route_type': plan.route_type,
            'action_type': plan.action_type,
            'eligible_domains': [d.value if hasattr(d, 'value') else str(d) for d in plan.eligible_domains],
            'selected_domains': [d.value if hasattr(d, 'value') else str(d) for d in plan.selected_domains],
            'requires_quran_verification': plan.requires_quran_verification,
            'requires_quran_reference_resolution': plan.requires_quran_reference_resolution,
            'use_tafsir': plan.use_tafsir,
            'evidence_requirements': [e.value if hasattr(e, 'value') else str(e) for e in plan.evidence_requirements],
            'should_abstain': plan.should_abstain,
            'abstain_reason': plan.abstain_reason.value if plan.abstain_reason else None,
            'tafsir_requested': plan.tafsir_requested,
            'tafsir_explicit': plan.tafsir_explicit,
            'hadith_requested': plan.hadith_requested,
            'topical_query': plan.topical_query,
            'notes': list(plan.notes),
            'repository_mode': plan.repository_mode,
            'source_resolution_strategy': plan.source_resolution_strategy,
            'quran_work_source_id': plan.quran_work_source_id,
            'translation_work_source_id': plan.translation_work_source_id,
            'requested_quran_work_source_id': plan.requested_quran_work_source_id,
            'requested_translation_work_source_id': plan.requested_translation_work_source_id,
            'requested_hadith_source_id': plan.requested_hadith_source_id,
            'quran_text_source_origin': plan.quran_text_source_origin,
            'quran_translation_source_origin': plan.quran_translation_source_origin,
            'source_policy': source_policy,
        },
        'route': plan.route,
        'resolution': evidence.resolution,
        'verifier_result': evidence.verifier_result,
        'warnings': evidence.warnings,
        'errors': evidence.errors,
        'raw_quran': evidence.quran.raw if evidence.quran else None,
        'raw_hadith': evidence.hadith.raw if evidence.hadith else None,
        'runtime_diagnostics': evidence.diagnostics,
        'raw_tafsir': [
            {
                'canonical_section_id': getattr(item.hit, 'canonical_section_id', None),
                'text_plain': getattr(item.hit, 'text_plain', None),
                'coverage_mode': getattr(item.hit, 'coverage_mode', 'lexical_topic_match'),
                'coverage_confidence': getattr(item.hit, 'coverage_confidence', getattr(item.hit, 'score', None)),
            }
            for item in evidence.tafsir
        ],
        'orchestration': orchestration,
        'conversation': conversation,
    }


def _derive_partial_success(plan: AskPlan, evidence: EvidencePack) -> bool:
    if plan.response_mode == ResponseMode.CLARIFY:
        return False
    if plan.response_mode == ResponseMode.TOPICAL_MULTI_SOURCE:
        return (bool(evidence.tafsir) != bool(evidence.hadith)) or bool(evidence.warnings)
    if plan.response_mode == ResponseMode.TOPICAL_TAFSIR:
        return not bool(evidence.tafsir) and bool(evidence.warnings or evidence.errors)
    if plan.response_mode == ResponseMode.TOPICAL_HADITH:
        return evidence.hadith is None and bool(evidence.warnings or evidence.errors)
    if plan.hadith_plan is not None and plan.route_type != 'topical_hadith_query':
        return evidence.hadith is not None and bool(evidence.warnings)
    if evidence.quran is None:
        return False
    if plan.use_tafsir and not evidence.tafsir and bool(evidence.warnings or evidence.errors):
        return True
    return False


def build_explain_answer_payload(plan: AskPlan, evidence: EvidencePack) -> dict[str, Any]:
    citations = render_citation_list(evidence)
    quran_support = _build_quran_support(plan, evidence)
    hadith_support = _build_hadith_support(evidence)
    tafsir_support = _build_tafsir_support(evidence)
    answer_text = _build_answer_text(plan, evidence)
    partial_success = _derive_partial_success(plan, evidence)
    source_policy = _build_source_policy(plan)

    error = None
    if plan.should_abstain and not quran_support and not hadith_support and not tafsir_support:
        error = plan.abstain_reason.value if plan.abstain_reason else None
    elif plan.response_mode in {ResponseMode.TOPICAL_TAFSIR, ResponseMode.TOPICAL_HADITH, ResponseMode.TOPICAL_MULTI_SOURCE} and not quran_support and not hadith_support and not tafsir_support and evidence.errors:
        error = evidence.errors[0]
    elif evidence.hadith is None and plan.hadith_plan is not None and evidence.errors:
        error = evidence.errors[0]
    elif evidence.quran is None and evidence.errors and plan.quran_plan is not None:
        error = evidence.errors[0]

    orchestration_payload = _build_orchestration_payload(
        plan,
        evidence,
        answer_text=answer_text,
        tafsir_support=tafsir_support,
        source_policy=source_policy,
        partial_success=partial_success,
    )
    debug_payload = _build_debug(
        plan,
        evidence,
        source_policy=source_policy,
        orchestration=orchestration_payload,
        conversation=(orchestration_payload.get('conversation') if isinstance(orchestration_payload, dict) else None),
    )

    payload = make_explain_answer_payload(
        ok=bool(answer_text or quran_support or hadith_support or tafsir_support) and not bool(plan.should_abstain and not quran_support and not hadith_support and not tafsir_support),
        query=plan.query,
        answer_mode=plan.response_mode.value if hasattr(plan.response_mode, 'value') else str(plan.response_mode),
        route_type=plan.route_type,
        action_type=plan.action_type,
        answer_text=answer_text,
        citations=citations,
        quran_support=quran_support,
        hadith_support=hadith_support,
        tafsir_support=tafsir_support,
        resolution=evidence.resolution,
        partial_success=partial_success,
        warnings=(['clarification_required'] if plan.response_mode == ResponseMode.CLARIFY else []) + list(evidence.warnings),
        debug=debug_payload,
        error=error,
        quran_source_selection=_build_quran_source_selection(plan),
        source_policy=source_policy,
        orchestration=orchestration_payload,
        conversation=(orchestration_payload.get('conversation') if isinstance(orchestration_payload, dict) else None),
    )
    payload['quran_span'] = evidence.quran.raw if evidence.quran else None
    payload['verifier_result'] = evidence.verifier_result
    payload['quote_payload'] = evidence.quote_payload
    payload['hadith_entry'] = _build_legacy_hadith_entry(evidence)
    return payload
