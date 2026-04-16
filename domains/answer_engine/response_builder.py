from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from domains.answer_engine.citation_renderer import render_citation_list
from domains.answer_engine.contracts import make_explain_answer_payload
from domains.answer_engine.composition_builder import build_composition_packet
from domains.answer_engine.conversational_renderer import render_bounded_conversational_answer
from domains.answer_engine.evidence_pack import EvidencePack
from domains.answer_engine.evidence_readiness import assess_evidence_readiness
from domains.answer_engine.excerpting import build_tafsir_excerpt
from domains.answer_engine.orchestration_contract import build_orchestration_envelope, serialize_contract
from domains.tafsir.tafheem_notes import build_tafheem_render_payload
from domains.ask.planner_types import AskPlan, AbstentionReason, ResponseMode, TerminalState


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
        'llm_composition_ready': bool(raw.get('llm_composition_ready')) or bool(raw.get('source_excerpt') or hadith.snippet or raw.get('guidance_summary') or hadith.english_text),
        'numbering_quality': numbering_quality,
    }


def _resolve_tafsir_render_payload(hit: Any) -> dict[str, Any]:
    source_id = str(getattr(hit, 'source_id', '') or '')
    fallback_text_plain = str(getattr(hit, 'text_plain', '') or '')
    fallback_text_html = getattr(hit, 'text_html', None)
    raw_json = dict(getattr(hit, 'raw_json', {}) or {})

    if source_id == 'tafsir:tafheem-al-quran-en':
        return build_tafheem_render_payload(
            raw_json=raw_json,
            fallback_text_plain=fallback_text_plain,
            fallback_text_html=fallback_text_html,
        )

    return {
        'display_text': fallback_text_plain,
        'excerpt_source_text': fallback_text_plain,
        'text_html': fallback_text_html,
        'inline_note_count': int(raw_json.get('inline_note_count') or 0),
        'rendering_mode': 'stored_text',
    }


def _build_tafsir_support(evidence: EvidencePack) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tafsir in evidence.tafsir:
        hit = tafsir.hit
        render_payload = _resolve_tafsir_render_payload(hit)
        prebuilt_snippet = getattr(hit, 'snippet', None)
        if prebuilt_snippet:
            excerpt = str(prebuilt_snippet)
            trimmed = False
        else:
            excerpt_source_text = str(render_payload.get('excerpt_source_text') or getattr(hit, 'text_plain', '') or '')
            excerpt, trimmed = build_tafsir_excerpt(excerpt_source_text)
        items.append(
            {
                'source_id': getattr(hit, 'source_id', None),
                'canonical_section_id': getattr(hit, 'canonical_section_id', None),
                'display_text': f"{getattr(hit, 'citation_label', 'Tafsir')} on Quran {getattr(hit, 'quran_span_ref', '')}",
                'citation_label': getattr(hit, 'citation_label', None),
                'display_name': getattr(hit, 'display_name', None),
                'excerpt': excerpt,
                'text_html': render_payload.get('text_html'),
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
                'rendering_mode': render_payload.get('rendering_mode'),
                'inline_note_count': render_payload.get('inline_note_count'),
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




_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def _take_sentences(text: str, *, max_sentences: int = 2, max_chars: int = 320) -> str:
    normalized = ' '.join((text or '').split()).strip()
    if not normalized:
        return ''
    parts = [segment.strip() for segment in _SENTENCE_SPLIT_RE.split(normalized) if segment.strip()]
    if not parts:
        return _condense_translation(normalized, limit=max_chars)
    selected: list[str] = []
    for part in parts:
        candidate = ' '.join(selected + [part]).strip()
        if len(candidate) > max_chars and selected:
            break
        selected.append(part)
        if len(selected) >= max_sentences or len(candidate) >= max_chars:
            break
    combined = ' '.join(selected).strip()
    if len(combined) <= max_chars:
        return combined
    return _condense_translation(combined, limit=max_chars)


def _humanize_hadith_collection(raw: dict[str, Any]) -> str:
    slug = str(raw.get('collection_slug') or raw.get('collection_source_id') or '').strip().lower()
    mapping = {
        'sahih-al-bukhari-en': 'Sahih al-Bukhari',
        'sahih-al-bukhari': 'Sahih al-Bukhari',
        'sahih-muslim-en': 'Sahih Muslim',
        'sahih-muslim': 'Sahih Muslim',
    }
    if slug in mapping:
        return mapping[slug]
    cleaned = slug.split(':')[-1].replace('-en', '').replace('-', ' ').strip()
    return cleaned.title() if cleaned else 'Hadith source'


def _build_hadith_explanation_seed(raw: dict[str, Any]) -> str:
    guidance = ' '.join(str(raw.get('guidance_summary') or '').split()).strip()
    if guidance:
        return _condense_translation(guidance, limit=280)
    snippet = ' '.join(str(raw.get('snippet') or '').split()).strip()
    if snippet:
        return _condense_translation(snippet, limit=280)
    excerpt = ' '.join(str(raw.get('source_excerpt') or '').split()).strip()
    if excerpt:
        return _take_sentences(excerpt, max_sentences=2, max_chars=280)
    english_text = ' '.join(str(raw.get('english_text') or '').split()).strip()
    if english_text:
        return _take_sentences(english_text, max_sentences=2, max_chars=280)
    return ''


def _unique_tafsir_labels(evidence: EvidencePack) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for item in evidence.tafsir:
        label = ' '.join(str(getattr(item.hit, 'citation_label', '') or '').split()).strip() or 'Tafsir'
        if label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels


def _join_labels(labels: list[str]) -> str:
    if not labels:
        return 'Tafsir'
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f'{labels[0]} and {labels[1]}'
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"

def _build_quran_with_tafsir_answer(plan: AskPlan, evidence: EvidencePack) -> str | None:
    del plan
    quran = evidence.quran
    if quran is None or not evidence.tafsir:
        return None

    first_tafsir = evidence.tafsir[0].hit
    tafsir_labels = _unique_tafsir_labels(evidence)
    label_text = _join_labels(tafsir_labels)
    translation_text = _condense_translation(quran.translation_text or '')
    if translation_text:
        return (
            f'{quran.citation_string} says: {translation_text} '
            f'Retrieved commentary from {label_text} is attached below.'
        ).strip()
    return f'Retrieved commentary from {label_text} on {quran.citation_string} is attached below.'.strip()


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
    summary = _build_hadith_explanation_seed({
        'guidance_summary': (hadith.raw or {}).get('guidance_summary'),
        'snippet': hadith.snippet,
        'source_excerpt': (hadith.raw or {}).get('source_excerpt'),
        'english_text': hadith.english_text,
    })
    collection_name = _humanize_hadith_collection({
        'collection_slug': hadith.collection_slug,
        'collection_source_id': hadith.collection_source_id,
    })
    if plan.response_mode == ResponseMode.HADITH_TEXT:
        if narrator:
            return f'{hadith.citation_string}: {narrator} {text}'.strip()
        return f'{hadith.citation_string}: {text}'.strip()
    if plan.response_mode == ResponseMode.HADITH_EXPLANATION:
        lead = summary or _take_sentences(text, max_sentences=2, max_chars=260)
        if lead:
            return (
                f'{collection_name}, {hadith.citation_string} indicates: {lead} '
                f'The full narration is provided below as the grounding source.'
            ).strip()
        if narrator and text:
            return (
                f'{collection_name}, {hadith.citation_string} reports {narrator}. '
                f'The full narration is provided below as the grounding source.'
            ).strip()
        return f'{collection_name}, {hadith.citation_string} was retrieved. The full narration is provided below as the grounding source.'.strip()
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


def _build_answer_text(plan: AskPlan, evidence: EvidencePack) -> str | None:
    if plan.response_mode == ResponseMode.ABSTAIN:
        hadith_policy = getattr(getattr(plan, 'source_policy', None), 'hadith', None)
        if hadith_policy is not None and getattr(hadith_policy, 'policy_reason', None) == 'topical_hadith_temporarily_disabled':
            return 'Topical Hadith answers are temporarily disabled in this release. Direct Hadith references such as “Bukhari 20” are still supported.'
        return None
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


def _build_quran_source_selection(plan: AskPlan, evidence: EvidencePack) -> dict[str, Any] | None:
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
        'selected_quran_text_source_id': (evidence.quran.quran_source_id if evidence.quran and evidence.quran.quran_source_id else plan.quran_work_source_id),
        'selected_quran_translation_source_id': (evidence.quran.translation_source_id if evidence.quran and evidence.quran.translation_source_id else plan.translation_work_source_id),
    }


def _build_source_policy(plan: AskPlan, evidence: EvidencePack) -> dict[str, Any] | None:
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
            'selected_text_source_id': (evidence.quran.quran_source_id if evidence.quran and evidence.quran.quran_source_id else quran_policy.selected_text_source_id),
            'selected_translation_source_id': (evidence.quran.translation_source_id if evidence.quran and evidence.quran.translation_source_id else quran_policy.selected_translation_source_id),
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
            'requested_source_ids': list(getattr(tafsir_policy, 'requested_source_ids', []) or []),
            'selected_source_id': tafsir_policy.selected_source_id,
            'selected_source_ids': list(getattr(tafsir_policy, 'selected_source_ids', []) or []),
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




def _terminal_state_for_plan(plan: AskPlan) -> str:
    if bool(getattr(plan, 'followup_rejected', False)):
        return TerminalState.ABSTAIN.value
    terminal_state = getattr(plan, 'terminal_state', None)
    if terminal_state is not None:
        return terminal_state.value if hasattr(terminal_state, 'value') else str(terminal_state)
    if plan.response_mode == ResponseMode.CLARIFY:
        return TerminalState.CLARIFY.value
    if plan.should_abstain or plan.response_mode == ResponseMode.ABSTAIN:
        return TerminalState.ABSTAIN.value
    return TerminalState.ANSWERED.value


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
    source_policy = _build_source_policy(plan, evidence)
    readiness = assess_evidence_readiness(
        plan=plan,
        quran_support=quran_support,
        hadith_support=hadith_support,
        tafsir_support=tafsir_support,
        verifier_result=evidence.verifier_result,
    )

    effective_plan = plan
    extra_warnings: list[str] = []
    if readiness.force_abstain:
        effective_plan = replace(
            plan,
            response_mode=ResponseMode.ABSTAIN,
            terminal_state=TerminalState.ABSTAIN,
            should_abstain=True,
            abstain_reason=AbstentionReason.INSUFFICIENT_EVIDENCE,
        )
        answer_text = readiness.safe_user_message or answer_text
        partial_success = partial_success or readiness.partial_evidence_present
        extra_warnings.append('insufficient_evidence')

    error = None
    if effective_plan.should_abstain and not quran_support and not hadith_support and not tafsir_support:
        error = effective_plan.abstain_reason.value if effective_plan.abstain_reason else None
    elif readiness.force_abstain:
        error = readiness.reason_code or 'insufficient_evidence'
    elif effective_plan.response_mode in {ResponseMode.TOPICAL_TAFSIR, ResponseMode.TOPICAL_HADITH, ResponseMode.TOPICAL_MULTI_SOURCE} and not quran_support and not hadith_support and not tafsir_support and evidence.errors:
        error = evidence.errors[0]
    elif evidence.hadith is None and effective_plan.hadith_plan is not None and evidence.errors:
        error = evidence.errors[0]
    elif evidence.quran is None and evidence.errors and effective_plan.quran_plan is not None:
        error = evidence.errors[0]

    pre_render_orchestration = _build_orchestration_payload(
        effective_plan,
        evidence,
        answer_text=answer_text,
        tafsir_support=tafsir_support,
        source_policy=source_policy,
        partial_success=partial_success,
    )

    conversation_payload = pre_render_orchestration.get('conversation') if isinstance(pre_render_orchestration, dict) else None
    composition_payload = build_composition_packet(
        plan=effective_plan,
        evidence=evidence,
        answer_text=answer_text,
        quran_support=quran_support,
        hadith_support=hadith_support,
        tafsir_support=tafsir_support,
        source_policy=source_policy,
        conversation=conversation_payload,
    )

    rendered_answer = render_bounded_conversational_answer(
        payload={
            'route_type': effective_plan.route_type,
            'action_type': effective_plan.action_type,
            'composition': composition_payload,
            'source_policy': source_policy,
            'conversation': conversation_payload,
        },
        fallback_answer_text=answer_text,
    )
    answer_text = rendered_answer.get('answer_text') or answer_text
    followup_suggestions = [str(item).strip() for item in list(rendered_answer.get('followup_suggestions') or []) if str(item).strip()]
    if isinstance(conversation_payload, dict) and followup_suggestions:
        conversation_payload['suggested_followups'] = followup_suggestions
    if isinstance(composition_payload, dict):
        abstention_packet = composition_payload.get('abstention')
        if readiness.force_abstain and isinstance(abstention_packet, dict):
            abstention_packet['reason_code'] = readiness.reason_code or abstention_packet.get('reason_code')
            abstention_packet['safe_user_message'] = readiness.safe_user_message or abstention_packet.get('safe_user_message')
            abstention_packet['next_supported_actions'] = list(readiness.next_supported_actions)
        followup_packet = composition_payload.get('followup')
        if isinstance(followup_packet, dict) and followup_suggestions:
            followup_packet['suggested_followups'] = followup_suggestions
        if effective_plan.followup_action_type or effective_plan.followup_rejected:
            composition_payload['active_followup_action'] = {
                'action_type': effective_plan.followup_action_type,
                'target_domain': effective_plan.followup_target_domain,
                'target_source_id': effective_plan.followup_target_source_id,
                'target_ref': effective_plan.followup_target_ref,
                'reason': effective_plan.followup_reason,
                'rejected': bool(effective_plan.followup_rejected),
            }

    terminal_state = _terminal_state_for_plan(effective_plan)
    if effective_plan.followup_rejected and terminal_state == TerminalState.ABSTAIN.value:
        followup_suggestions = []
        if isinstance(conversation_payload, dict):
            conversation_payload['followup_ready'] = False
            conversation_payload['suggested_followups'] = []
        if isinstance(composition_payload, dict):
            composition_payload['terminal_state'] = TerminalState.ABSTAIN.value
            followup_packet = composition_payload.get('followup')
            if isinstance(followup_packet, dict):
                followup_packet['followup_ready'] = False
                followup_packet['suggested_followups'] = []
            abstention_packet = composition_payload.get('abstention')
            if isinstance(abstention_packet, dict) and effective_plan.followup_reason:
                abstention_packet['reason_code'] = effective_plan.followup_reason

    orchestration_payload = _build_orchestration_payload(
        effective_plan,
        evidence,
        answer_text=answer_text,
        tafsir_support=tafsir_support,
        source_policy=source_policy,
        partial_success=partial_success,
    )
    if isinstance(orchestration_payload, dict):
        diagnostics = orchestration_payload.get('diagnostics')
        if isinstance(diagnostics, dict):
            diagnostics['render_mode'] = rendered_answer.get('render_mode')
            diagnostics['renderer_version'] = rendered_answer.get('renderer_version')
            diagnostics['renderer_backend'] = rendered_answer.get('renderer_backend')

    debug_payload = _build_debug(
        effective_plan,
        evidence,
        source_policy=source_policy,
        orchestration=orchestration_payload,
        conversation=(orchestration_payload.get('conversation') if isinstance(orchestration_payload, dict) else None),
    )

    payload = make_explain_answer_payload(
        ok=(not effective_plan.should_abstain) and bool(answer_text or quran_support or hadith_support or tafsir_support),
        query=effective_plan.query,
        answer_mode=effective_plan.response_mode.value if hasattr(effective_plan.response_mode, 'value') else str(effective_plan.response_mode),
        terminal_state=terminal_state,
        route_type=effective_plan.route_type,
        action_type=effective_plan.action_type,
        answer_text=answer_text,
        citations=citations,
        quran_support=quran_support,
        hadith_support=hadith_support,
        tafsir_support=tafsir_support,
        resolution=evidence.resolution,
        partial_success=partial_success,
        warnings=(['clarification_required'] if effective_plan.response_mode == ResponseMode.CLARIFY else []) + extra_warnings + list(evidence.warnings),
        debug=debug_payload,
        error=error,
        quran_source_selection=_build_quran_source_selection(effective_plan, evidence),
        source_policy=source_policy,
        orchestration=orchestration_payload,
        conversation=conversation_payload,
        composition=composition_payload,
    )
    payload['quran_span'] = evidence.quran.raw if evidence.quran else None
    payload['verifier_result'] = evidence.verifier_result
    payload['quote_payload'] = evidence.quote_payload
    payload['hadith_entry'] = _build_legacy_hadith_entry(evidence)
    return payload
