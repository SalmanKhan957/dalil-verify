from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from domains.answer_engine.evidence_pack import EvidencePack
from domains.answer_engine.evidence_readiness import assess_evidence_readiness
from domains.ask.planner_types import AskPlan, ResponseMode, TerminalState
from domains.conversation.followup_capabilities import FollowupAction, derive_followup_capabilities
from domains.conversation.followup_phrasebook import render_suggested_followups
from domains.conversation.session_state import ActiveScope, ConversationAnchorSet, SessionState


_COMPOSITION_MODE_MAP = {
    ResponseMode.VERIFICATION_ONLY: 'verification_only',
    ResponseMode.VERIFICATION_THEN_EXPLAIN: 'verification_then_explain',
    ResponseMode.QURAN_WITH_TAFSIR: 'quran_with_tafsir',
    ResponseMode.HADITH_TEXT: 'hadith_text',
    ResponseMode.HADITH_EXPLANATION: 'hadith_explanation',
    ResponseMode.CLARIFY: 'clarify',
    ResponseMode.ABSTAIN: 'abstain',
    ResponseMode.QURAN_TEXT: 'quran_text',
    ResponseMode.QURAN_EXPLANATION: 'quran_explanation',
    ResponseMode.TOPICAL_TAFSIR: 'topical_tafsir',
    ResponseMode.TOPICAL_HADITH: 'topical_hadith',
    ResponseMode.TOPICAL_MULTI_SOURCE: 'topical_multi_source',
}

_HTML_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def _collapse_whitespace(value: Any) -> str:
    return _WS_RE.sub(' ', str(value or '')).strip()


def _strip_html(value: Any) -> str:
    text = str(value or '')
    if not text:
        return ''
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p\s*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</div\s*>', '\n', text, flags=re.IGNORECASE)
    text = _HTML_TAG_RE.sub(' ', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    # preserve paragraph breaks lightly
    text = re.sub(r'\n\s*\n\s*', '\n\n', text)
    return text.strip()


def _truncate_text(text: str, *, limit: int, ellipsis: str = '…') -> str:
    normalized = text.strip()
    if not normalized:
        return ''
    if len(normalized) <= limit:
        return normalized
    cut = normalized[:limit]
    for delimiter in ('. ', '; ', ', ', ' '):
        idx = cut.rfind(delimiter)
        if idx >= int(limit * 0.6):
            cut = cut[:idx].strip()
            break
    return cut.rstrip(' ,;:-') + ellipsis


def _build_focused_extract(*candidates: str, fallback: str = '', limit: int = 1200) -> str:
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized:
            continue
        if len(normalized) <= limit:
            return normalized
        return _truncate_text(normalized, limit=limit)
    return _truncate_text(fallback, limit=limit) if fallback else ''


def _short_excerpt(*candidates: str, fallback: str = '', limit: int = 260) -> str:
    for candidate in candidates:
        normalized = _collapse_whitespace(candidate)
        if normalized:
            return _truncate_text(normalized, limit=limit)
    normalized_fallback = _collapse_whitespace(fallback)
    return _truncate_text(normalized_fallback, limit=limit) if normalized_fallback else ''


def _humanize_source_id(value: str | None) -> str:
    text = _collapse_whitespace(value)
    if not text:
        return 'Source'
    slug = text.split(':')[-1].replace('-', ' ')
    return slug.title()


def _humanize_collection_name(*, source_id: str | None = None, collection_slug: str | None = None) -> str:
    slug = _collapse_whitespace(collection_slug) or _collapse_whitespace(source_id).split(':')[-1]
    slug = slug.replace('_', '-').strip().lower()
    known = {
        'sahih-al-bukhari-en': 'Sahih al-Bukhari',
        'sahih-al-bukhari': 'Sahih al-Bukhari',
        'sahih-muslim-en': 'Sahih Muslim',
        'sahih-muslim': 'Sahih Muslim',
        'riyad-as-salihin-en': 'Riyad as-Salihin',
        'riyad-as-salihin': 'Riyad as-Salihin',
    }
    if slug in known:
        return known[slug]
    cleaned = slug.replace('-en', '').replace('-', ' ').strip()
    if not cleaned:
        return 'Hadith source'
    return cleaned.title()


def _take_sentences(text: str, *, max_sentences: int = 2, max_chars: int = 320) -> str:
    normalized = _collapse_whitespace(text)
    if not normalized:
        return ''
    parts = [segment.strip() for segment in _SENTENCE_SPLIT_RE.split(normalized) if segment.strip()]
    if not parts:
        return _truncate_text(normalized, limit=max_chars)
    selected = []
    total = 0
    for part in parts:
        if not part:
            continue
        candidate = ((' '.join(selected + [part])).strip())
        if len(candidate) > max_chars and selected:
            break
        selected.append(part)
        total += 1
        if total >= max_sentences or len(candidate) >= max_chars:
            break
    return _truncate_text(' '.join(selected).strip(), limit=max_chars)


def _build_hadith_summary(hadith_support: dict[str, Any] | None, *, max_chars: int = 320) -> str:
    if hadith_support is None:
        return ''
    guidance_summary = _collapse_whitespace(hadith_support.get('guidance_summary'))
    if guidance_summary:
        return _truncate_text(guidance_summary, limit=max_chars)
    snippet = _collapse_whitespace(hadith_support.get('snippet'))
    if snippet:
        return _truncate_text(snippet, limit=max_chars)
    source_excerpt = _collapse_whitespace(hadith_support.get('source_excerpt'))
    if source_excerpt:
        return _take_sentences(source_excerpt, max_sentences=2, max_chars=max_chars)
    english_text = _collapse_whitespace(hadith_support.get('english_text'))
    if english_text:
        return _take_sentences(english_text, max_sentences=2, max_chars=max_chars)
    return ''


def _build_hadith_takeaways(hadith_support: dict[str, Any] | None) -> list[str]:
    if hadith_support is None:
        return []
    candidates = [
        _collapse_whitespace(hadith_support.get('guidance_summary')),
        _collapse_whitespace(hadith_support.get('snippet')),
        _take_sentences(_collapse_whitespace(hadith_support.get('source_excerpt')), max_sentences=1, max_chars=220),
        _take_sentences(_collapse_whitespace(hadith_support.get('english_text')), max_sentences=1, max_chars=220),
    ]
    takeaways: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        cleaned = _truncate_text(candidate, limit=220)
        if cleaned and cleaned not in takeaways:
            takeaways.append(cleaned)
        if len(takeaways) >= 3:
            break
    return takeaways


def _composition_mode(plan: AskPlan) -> str:
    return _COMPOSITION_MODE_MAP.get(plan.response_mode, str(getattr(plan.response_mode, 'value', plan.response_mode)))


def _terminal_state(plan: AskPlan) -> str:
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


def _resolved_scope(plan: AskPlan, evidence: EvidencePack, quran_support: dict[str, Any] | None, hadith_support: dict[str, Any] | None) -> dict[str, Any]:
    scope: dict[str, Any] = {
        'primary_domain': None,
        'route_type': plan.route_type,
        'action_type': plan.action_type,
        'canonical_refs': [],
        'query_normalized': str((plan.route or {}).get('normalized_query') or plan.query),
    }
    if quran_support is not None:
        scope.update({
            'primary_domain': 'quran',
            'canonical_refs': [str(quran_support.get('canonical_source_id') or '')],
            'surah_no': quran_support.get('surah_no'),
            'ayah_start': quran_support.get('ayah_start'),
            'ayah_end': quran_support.get('ayah_end'),
            'span_label': quran_support.get('citation_string'),
        })
        return scope
    best_match = (evidence.verifier_result or {}).get('best_match') or {}
    if best_match:
        scope.update({
            'primary_domain': 'quran',
            'canonical_refs': [str(best_match.get('canonical_source_id') or '')],
            'span_label': best_match.get('citation'),
            'surah_no': best_match.get('surah_no'),
            'ayah_start': best_match.get('start_ayah'),
            'ayah_end': best_match.get('end_ayah'),
        })
        return scope
    if hadith_support is not None:
        canonical_ref = str(hadith_support.get('canonical_ref') or '').strip()
        supporting_refs = [str(ref).strip() for ref in list(hadith_support.get('supporting_refs') or []) if str(ref).strip()]
        refs = [canonical_ref] if canonical_ref else []
        if supporting_refs:
            refs.extend(ref for ref in supporting_refs if ref not in refs)
        scope.update({
            'primary_domain': 'hadith',
            'canonical_refs': refs,
            'collection_source_id': hadith_support.get('collection_source_id'),
            'public_ref_label': hadith_support.get('citation_string'),
            'book_number': hadith_support.get('book_number'),
            'chapter_number': hadith_support.get('chapter_number'),
            'in_book_hadith_number': hadith_support.get('in_book_hadith_number'),
        })
        return scope
    route_type = str(plan.route_type or '')
    if 'hadith' in route_type:
        scope['primary_domain'] = 'hadith'
    elif any(token in route_type for token in ('quran', 'tafsir')):
        scope['primary_domain'] = 'quran'
    return scope


def _answer_seed(plan: AskPlan, answer_text: str | None, quran_support: dict[str, Any] | None, hadith_support: dict[str, Any] | None) -> dict[str, Any]:
    if plan.response_mode in {ResponseMode.HADITH_TEXT, ResponseMode.HADITH_EXPLANATION, ResponseMode.TOPICAL_HADITH} and hadith_support is not None:
        lead_text = _build_hadith_summary(hadith_support, max_chars=320)
    else:
        lead_text = _truncate_text(_collapse_whitespace(answer_text), limit=380) if answer_text else answer_text
    seed: dict[str, Any] = {
        'lead_text': lead_text,
        'summary_style': 'source_grounded',
        'must_preserve_boundaries': True,
    }
    if quran_support is not None:
        base_text = _collapse_whitespace(quran_support.get('translation_text') or quran_support.get('arabic_text'))
        seed['base_quote'] = {
            'domain': 'quran',
            'canonical_ref': quran_support.get('canonical_source_id'),
            'text': _short_excerpt(base_text, limit=320),
        }
    elif hadith_support is not None:
        hadith_text = _collapse_whitespace(hadith_support.get('source_excerpt') or hadith_support.get('snippet') or hadith_support.get('english_text'))
        seed['base_quote'] = {
            'domain': 'hadith',
            'canonical_ref': hadith_support.get('canonical_ref'),
            'text': _short_excerpt(hadith_text, limit=320),
        }
        if plan.response_mode in {ResponseMode.HADITH_EXPLANATION, ResponseMode.TOPICAL_HADITH}:
            takeaways = _build_hadith_takeaways(hadith_support)
            if takeaways:
                seed['key_takeaways'] = takeaways
    return seed


def _quran_source_bundle(quran_support: dict[str, Any] | None, evidence: EvidencePack) -> list[dict[str, Any]]:
    if quran_support is None:
        best_match = (evidence.verifier_result or {}).get('best_match') or {}
        if not best_match:
            return []
        full_text = _collapse_whitespace(best_match.get('english_translation', {}).get('text') or best_match.get('text_display'))
        return [{
            'domain': 'quran',
            'source_id': best_match.get('source_id'),
            'display_name': 'Quran verification match',
            'role': 'verification_source',
            'scope_ref': best_match.get('canonical_source_id'),
            'text': full_text,
            'full_text': full_text,
            'focused_extract': _build_focused_extract(full_text, limit=1400),
            'short_excerpt': _short_excerpt(full_text),
            'citation': best_match.get('citation'),
            'citations': [best_match.get('canonical_source_id')],
        }]
    full_text = _collapse_whitespace(quran_support.get('translation_text') or quran_support.get('arabic_text'))
    return [{
        'domain': 'quran',
        'source_id': quran_support.get('quran_source_id'),
        'display_name': quran_support.get('citation_string'),
        'role': 'quran_source',
        'scope_ref': quran_support.get('canonical_source_id'),
        'text': full_text,
        'full_text': full_text,
        'focused_extract': _build_focused_extract(full_text, limit=1400),
        'short_excerpt': _short_excerpt(full_text),
        'arabic_text': quran_support.get('arabic_text'),
        'translation_text': quran_support.get('translation_text'),
        'citations': [quran_support.get('canonical_source_id')],
    }]


def _tafsir_source_bundles(tafsir_support: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in tafsir_support:
        grouped[str(item.get('source_id') or 'unknown')].append(item)
    bundles: list[dict[str, Any]] = []
    total_groups = len(grouped)
    for source_id, items in grouped.items():
        full_text_parts: list[str] = []
        focused_candidates: list[str] = []
        short_candidates: list[str] = []
        units: list[dict[str, Any]] = []
        for item in items:
            plain_text = _strip_html(item.get('text_html')) or _collapse_whitespace(item.get('excerpt'))
            excerpt = _collapse_whitespace(item.get('excerpt'))
            if plain_text:
                full_text_parts.append(plain_text)
            if excerpt:
                focused_candidates.append(excerpt)
                short_candidates.append(excerpt)
            units.append({
                'canonical_ref': item.get('canonical_section_id'),
                'display_text': item.get('display_text'),
                'excerpt': item.get('excerpt'),
                'quran_span_ref': item.get('quran_span_ref'),
                'rendering_mode': item.get('rendering_mode'),
            })
        full_text = '\n\n'.join(part for part in full_text_parts if part).strip()
        focused_extract = _build_focused_extract(*focused_candidates, fallback=full_text, limit=1400)
        short_excerpt = _short_excerpt(*short_candidates, fallback=focused_extract, limit=260)
        bundles.append({
            'domain': 'tafsir',
            'source_id': source_id,
            'display_name': items[0].get('display_name') or items[0].get('citation_label') or _humanize_source_id(source_id),
            'role': 'comparative_commentary' if total_groups > 1 else 'tafsir_commentary',
            'scope_ref': items[0].get('canonical_section_id'),
            'full_text': full_text,
            'focused_extract': focused_extract,
            'short_excerpt': short_excerpt,
            'units': units,
            'merged_plaintext': focused_extract,
            'citations': [item.get('canonical_section_id') for item in items if item.get('canonical_section_id')],
        })
    return bundles


def _hadith_source_bundle(hadith_support: dict[str, Any] | None, composition_mode: str) -> list[dict[str, Any]]:
    if hadith_support is None:
        return []
    full_text = ' '.join(
        part for part in [
            _collapse_whitespace(hadith_support.get('english_narrator')),
            _collapse_whitespace(hadith_support.get('english_text')),
        ] if part
    ).strip()
    summary = _build_hadith_summary(hadith_support, max_chars=420)
    focused_extract = _build_focused_extract(
        summary,
        _collapse_whitespace(hadith_support.get('source_excerpt')),
        _collapse_whitespace(hadith_support.get('snippet')),
        _collapse_whitespace(hadith_support.get('guidance_summary')),
        fallback=full_text,
        limit=900,
    )
    short_excerpt = _short_excerpt(
        summary,
        _collapse_whitespace(hadith_support.get('source_excerpt')),
        _collapse_whitespace(hadith_support.get('snippet')),
        fallback=focused_extract,
        limit=220,
    )
    role = 'explicit_hadith_source'
    if composition_mode == 'topical_hadith':
        role = 'topical_hadith_source'
    bundle: dict[str, Any] = {
        'domain': 'hadith',
        'source_id': hadith_support.get('collection_source_id'),
        'display_name': _humanize_collection_name(
            source_id=hadith_support.get('collection_source_id'),
            collection_slug=hadith_support.get('collection_slug'),
        ),
        'role': role,
        'scope_ref': hadith_support.get('canonical_ref'),
        'full_text': full_text,
        'focused_extract': focused_extract,
        'short_excerpt': short_excerpt,
        'reference_url': hadith_support.get('reference_url'),
        'citations': [hadith_support.get('canonical_ref')],
    }
    supporting_refs = [str(ref).strip() for ref in list(hadith_support.get('supporting_refs') or []) if str(ref).strip()]
    if supporting_refs:
        bundle['supporting_refs'] = supporting_refs
    matched_topics = [str(topic).strip() for topic in list(hadith_support.get('matched_topics') or []) if str(topic).strip()]
    if matched_topics:
        bundle['matched_topics'] = matched_topics
    return [bundle]


def _comparative_packet(tafsir_bundles: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(tafsir_bundles) <= 1:
        return None
    return {
        'enabled': True,
        'source_ids': [bundle.get('source_id') for bundle in tafsir_bundles],
        'shared_points': [],
        'distinct_emphases': [
            {
                'source_id': bundle.get('source_id'),
                'points': [],
            }
            for bundle in tafsir_bundles
        ],
        'conflicts': [],
        'ready_for_llm_composition': True,
    }


def _followup_session_state(
    conversation: dict[str, Any] | None,
    *,
    composition_mode: str,
    quran_support: dict[str, Any] | None,
    hadith_support: dict[str, Any] | None,
    tafsir_support: list[dict[str, Any]],
    active_scope_summary: dict[str, Any] | None = None,
) -> SessionState:
    conversation = conversation or {}
    anchors = list(conversation.get('anchors') or [])
    anchor_set = ConversationAnchorSet.from_anchor_payload(anchors)
    summary = dict(active_scope_summary or {})
    domains: list[str] = [str(item).strip() for item in list(summary.get('domains') or []) if str(item).strip()]
    if quran_support and 'quran' not in domains:
        domains.append('quran')
    if tafsir_support and 'tafsir' not in domains:
        domains.append('tafsir')
    if hadith_support and 'hadith' not in domains:
        domains.append('hadith')
    displayed_tafsir_source_ids = [str(item.get('source_id') or '').strip() for item in list(tafsir_support or []) if str(item.get('source_id') or '').strip()]
    comparative_tafsir_source_ids = [str(item).strip() for item in list(summary.get('comparative_tafsir_source_ids') or []) if str(item).strip()] or list(displayed_tafsir_source_ids)
    current_tafsir_source_id = str(summary.get('current_tafsir_source_id') or '').strip() or (displayed_tafsir_source_ids[0] if len(displayed_tafsir_source_ids) == 1 else None)
    return SessionState(
        route_type=None,
        answer_mode=composition_mode,
        terminal_state=None,
        scope=ActiveScope(
            route_type=None,
            answer_mode=composition_mode,
            domains=domains,
            quran_ref=str((quran_support or {}).get('canonical_source_id') or summary.get('quran_ref') or '').strip() or None,
            quran_span_ref=str(summary.get('quran_span_ref') or (quran_support or {}).get('canonical_source_id') or '').strip() or None,
            tafsir_source_ids=displayed_tafsir_source_ids,
            comparative_tafsir_source_ids=comparative_tafsir_source_ids,
            current_tafsir_source_id=current_tafsir_source_id,
            hadith_ref=str((hadith_support or {}).get('canonical_ref') or summary.get('hadith_ref') or '').strip() or None,
            hadith_source_id=str((hadith_support or {}).get('collection_source_id') or summary.get('hadith_source_id') or '').strip() or None,
        ),
        anchors=anchor_set,
        citations=[],
        active_source_ids=[str(item.get('source_id') or '').strip() for item in list(tafsir_support or []) if str(item.get('source_id') or '').strip()],
        followup_ready=bool(conversation.get('followup_ready')),
        raw_context={},
    )



def _serialize_followup_capabilities(state: SessionState) -> list[dict[str, Any]]:
    items = []
    for capability in derive_followup_capabilities(state).sorted():
        items.append({
            'action_type': capability.action_type.value if hasattr(capability.action_type, 'value') else str(capability.action_type),
            'target_domain': capability.target_domain,
            'target_source_id': capability.target_source_id,
            'target_ref': capability.target_ref,
            'display_priority': capability.priority,
            'phrase_params': dict(capability.phrase_params),
        })
    return items



def _followup_packet(
    conversation: dict[str, Any] | None,
    composition_mode: str,
    *,
    quran_support: dict[str, Any] | None = None,
    hadith_support: dict[str, Any] | None = None,
    tafsir_support: list[dict[str, Any]] | None = None,
    source_bundles: list[dict[str, Any]] | None = None,
    terminal_state: str | None = None,
    followup_rejected: bool = False,
    active_scope_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conversation = conversation or {}
    active_refs = [str(item.get('canonical_ref') or '') for item in list(conversation.get('anchors') or []) if str(item.get('canonical_ref') or '').strip()]
    state = _followup_session_state(
        conversation,
        composition_mode=composition_mode,
        quran_support=quran_support,
        hadith_support=hadith_support,
        tafsir_support=list(tafsir_support or []),
        active_scope_summary=active_scope_summary,
    )
    capability_set = derive_followup_capabilities(state)
    suggestions = render_suggested_followups(capability_set)
    if followup_rejected or terminal_state == TerminalState.ABSTAIN.value:
        suggestions = []
    source_specific: list[str] = []
    span_specific: list[str] = []
    for capability, phrase in zip(capability_set.sorted(), suggestions):
        if capability.action_type == FollowupAction.FOCUS_SOURCE:
            source_specific.append(phrase)
        else:
            span_specific.append(phrase)
    return {
        'followup_ready': bool(conversation.get('followup_ready')) and not (followup_rejected or terminal_state == TerminalState.ABSTAIN.value),
        'runtime_statefulness': 'anchored_only' if active_refs else 'none',
        'active_anchor_refs': active_refs,
        'source_specific_followups_supported': source_specific,
        'span_specific_followups_supported': span_specific,
        'capabilities': _serialize_followup_capabilities(state),
        'suggested_followups': suggestions[:4],
        'active_scope_summary': {
            'domains': list(state.scope.domains),
            'quran_ref': state.scope.quran_ref,
            'quran_span_ref': state.scope.quran_span_ref,
            'tafsir_source_ids': list(state.scope.tafsir_source_ids),
            'comparative_tafsir_source_ids': list(state.scope.comparative_tafsir_source_ids),
            'current_tafsir_source_id': state.scope.current_tafsir_source_id,
            'hadith_ref': state.scope.hadith_ref,
            'hadith_source_id': state.scope.hadith_source_id,
        },
    }


def _policy_packet(plan: AskPlan, source_policy: dict[str, Any] | None, source_bundles: list[dict[str, Any]], terminal_state: str) -> dict[str, Any]:
    domains_included = [bundle.get('domain') for bundle in source_bundles if bundle.get('domain')]
    dedup_domains: list[str] = []
    for domain in domains_included:
        if domain not in dedup_domains:
            dedup_domains.append(domain)
    excluded = [domain for domain in ('quran', 'tafsir', 'hadith') if domain not in dedup_domains]
    source_public_scope = None
    if isinstance(source_policy, dict):
        hadith_policy = source_policy.get('hadith') or {}
        source_public_scope = hadith_policy.get('public_response_scope')
    return {
        'must_preserve_domain_boundaries': True,
        'domains_included': dedup_domains,
        'domains_excluded': excluded,
        'source_ids_allowed_for_composition': [bundle.get('source_id') for bundle in source_bundles if bundle.get('source_id')],
        'public_scope': 'bounded_source_grounded',
        'source_public_scope': source_public_scope,
        'composition_allowed': terminal_state == TerminalState.ANSWERED.value,
    }


def _clarification_packet(plan: AskPlan, terminal_state: str) -> dict[str, Any] | None:
    if terminal_state != TerminalState.CLARIFY.value:
        return None
    return {
        'reason_code': 'broad_query_requires_clarification',
        'prompt': plan.clarify_prompt,
        'suggested_topics': list(plan.clarify_topics),
    }


def _abstention_packet(plan: AskPlan, terminal_state: str, answer_text: str | None, source_policy: dict[str, Any] | None) -> dict[str, Any] | None:
    if terminal_state != TerminalState.ABSTAIN.value:
        return None
    reason_code = None
    hadith_policy_reason = None
    if isinstance(source_policy, dict):
        hadith_policy_reason = ((source_policy.get('hadith') or {}).get('policy_reason'))
    if hadith_policy_reason:
        reason_code = hadith_policy_reason
    elif bool(getattr(plan, 'followup_rejected', False)) and getattr(plan, 'followup_reason', None):
        reason_code = getattr(plan, 'followup_reason', None)
    elif plan.abstain_reason is not None:
        reason_code = plan.abstain_reason.value if hasattr(plan.abstain_reason, 'value') else str(plan.abstain_reason)
    else:
        reason_code = 'policy_restricted'
    next_supported_actions: list[str] = []
    safe_user_message = None
    active_scope_summary = dict(getattr(plan, 'active_scope_summary', {}) or {})
    scope_domains = {str(item).strip().lower() for item in list(active_scope_summary.get('domains') or []) if str(item).strip()}
    has_quran_scope = bool(active_scope_summary.get('quran_ref') or active_scope_summary.get('quran_span_ref') or 'quran' in scope_domains)
    has_hadith_scope = bool(active_scope_summary.get('hadith_ref') or 'hadith' in scope_domains)
    if reason_code == 'topical_hadith_temporarily_disabled':
        safe_user_message = 'Public topical Hadith is not enabled in the current bounded product surface.'
        next_supported_actions = ['Ask for an explicit hadith reference', 'Use a direct citation such as Bukhari 20']
    elif reason_code == 'followup_target_source_not_in_scope':
        safe_user_message = 'That tafsir source is not part of the current thread scope, so I should not jump to it automatically.'
        next_supported_actions = ['Ask about one of the sources already in scope', 'Ask to simplify the current explanation']
    elif reason_code == 'followup_span_not_available':
        if has_quran_scope:
            safe_user_message = 'That verse navigation move is not available from the current anchored span.'
            next_supported_actions = ['Ask about the current verse directly', 'Ask to simplify the current explanation']
        elif has_hadith_scope:
            safe_user_message = 'That verse navigation move is not available from the current hadith thread.'
            next_supported_actions = ['Ask about the current hadith directly', 'Ask to simplify the current explanation']
        else:
            safe_user_message = 'That navigation move is not available from the current anchored thread.'
            next_supported_actions = ['Ask about the current answer directly', 'Ask to simplify the current explanation']
    elif reason_code == 'followup_requires_new_query_boundary':
        if has_quran_scope:
            safe_user_message = 'That request changes the question boundary. Please ask it as a fresh direct query instead of continuing the current anchored verse thread.'
        elif has_hadith_scope:
            safe_user_message = 'That request changes the question boundary. Please ask it as a fresh direct query instead of continuing the current anchored hadith thread.'
        else:
            safe_user_message = 'That request changes the current question boundary. Please ask it as a fresh direct query.'
        next_supported_actions = ['Ask a new direct Quran or Hadith question', 'Use an explicit reference such as 2:255 or Bukhari 7']
    elif reason_code in {'followup_missing_anchor', 'followup_action_not_supported_for_scope'}:
        if has_hadith_scope and not has_quran_scope:
            safe_user_message = 'That follow-up action does not fit the current hadith thread.'
        elif has_quran_scope:
            safe_user_message = 'That follow-up action does not fit the current anchored verse thread.'
        else:
            safe_user_message = 'That follow-up action does not fit the current anchored scope.'
        next_supported_actions = ['Ask a direct Quran reference such as 2:255', 'Ask a direct hadith reference such as Bukhari 7']
    elif bool(getattr(plan, 'followup_rejected', False)):
        safe_user_message = 'I cannot continue that request inside the current anchored thread.'
    return {
        'reason_code': reason_code,
        'safe_user_message': safe_user_message if safe_user_message is not None else answer_text,
        'next_supported_actions': next_supported_actions,
    }


def _continuation_controls(plan: AskPlan, quran_support: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if quran_support is None:
        return None
    request_context = dict(getattr(plan, 'request_context', {}) or {})
    hydrated_state = request_context.get('_hydrated_session_state') if isinstance(request_context, dict) else None
    continuation_state = hydrated_state.get('scope', {}).get('continuation') if isinstance(hydrated_state, dict) else None

    cursor = 0
    total = 12
    if isinstance(continuation_state, dict):
        cursor = int(continuation_state.get('cursor_position') or 0)
        total = int(continuation_state.get('total_chunks') or 12)

    # Advance/retreat cursor based on continuation direction
    route = getattr(plan, 'route', {}) or {}
    if route.get('followup_kind') == 'continuation':
        direction = route.get('continuation_direction', 'forward')
        if direction == 'backward':
            cursor = max(0, cursor - 1)
        else:
            cursor += 1
        # Reset total_chunks on cross-surah advance
        if 'cross_surah_advance' in (route.get('signals') or []):
            surah_no = int((route.get('parsed_reference') or {}).get('surah_no') or 0)
            if surah_no > 0:
                from domains.ask.classifier import _SURAH_AYAH_COUNTS
                ayah_count = _SURAH_AYAH_COUNTS.get(surah_no, 0)
                total = max(1, (ayah_count + 4) // 5) if ayah_count else 12
                cursor = 0

    return {
        'source_id': str(plan.quran_work_source_id or 'quran:tanzil-simple'),
        'reference': f"quran:{quran_support.get('surah_no')}:{quran_support.get('ayah_start')}-{quran_support.get('ayah_end')}",
        'cursor_position': cursor,
        'total_chunks': total,
        'remaining_chunks': max(0, total - cursor),
        'continuation_mode': plan.response_mode.value,
        'truncate_large_responses': True,
        'max_allowed_paragraphs': 5,
        'offered_continuation_hook': "Would you like to continue reading the next section?",
    }

def _rendering_packet(plan: AskPlan) -> dict[str, Any]:
    preferences = dict(plan.request_preferences or {})
    return {
        'preferred_language': preferences.get('language') or 'en',
        'verbosity': preferences.get('verbosity') or 'standard',
        'citation_style': preferences.get('citations') or 'inline',
        'quote_length_policy': 'short_quote_plus_summary',
    }


def build_composition_packet(*, plan: AskPlan, evidence: EvidencePack, answer_text: str | None, quran_support: dict[str, Any] | None, hadith_support: dict[str, Any] | None, tafsir_support: list[dict[str, Any]], source_policy: dict[str, Any] | None, conversation: dict[str, Any] | None) -> dict[str, Any]:
    composition_mode = _composition_mode(plan)
    terminal_state = _terminal_state(plan)
    readiness = assess_evidence_readiness(
        plan=plan,
        quran_support=quran_support,
        hadith_support=hadith_support,
        tafsir_support=tafsir_support,
        verifier_result=evidence.verifier_result,
    )
    quran_bundles = _quran_source_bundle(quran_support, evidence) if composition_mode in {'verification_only', 'verification_then_explain', 'quran_text', 'quran_explanation', 'quran_with_tafsir'} else []
    tafsir_bundles = _tafsir_source_bundles(tafsir_support)
    hadith_bundles = _hadith_source_bundle(hadith_support, composition_mode)
    source_bundles = quran_bundles + tafsir_bundles + hadith_bundles
    return {
        'contract_version': 'ask.composition.v1',
        'llm_ready': readiness.llm_ready and terminal_state == TerminalState.ANSWERED.value,
        'composition_mode': composition_mode,
        'terminal_state': terminal_state,
        'resolved_scope': _resolved_scope(plan, evidence, quran_support, hadith_support),
        'answer_seed': _answer_seed(plan, answer_text, quran_support, hadith_support),
        'source_bundles': source_bundles,
        'comparative': _comparative_packet(tafsir_bundles),
        'followup': _followup_packet(
            conversation,
            composition_mode,
            quran_support=quran_support,
            hadith_support=hadith_support,
            tafsir_support=tafsir_support,
            source_bundles=source_bundles,
            terminal_state=terminal_state,
            followup_rejected=bool(getattr(plan, 'followup_rejected', False)),
            active_scope_summary=dict(getattr(plan, 'active_scope_summary', {}) or {}),
        ),
        'active_scope_summary': dict(getattr(plan, 'active_scope_summary', {}) or {}),
        'policy': _policy_packet(plan, source_policy, source_bundles, terminal_state),
        'continuation_controls': _continuation_controls(plan, quran_support),
        'clarification': _clarification_packet(plan, terminal_state),
        'abstention': _abstention_packet(plan, terminal_state, answer_text, source_policy),
        'rendering': _rendering_packet(plan),
        'evidence_readiness': {
            'answerable': readiness.answerable,
            'llm_ready': readiness.llm_ready,
            'force_abstain': readiness.force_abstain,
            'reason_code': readiness.reason_code,
            'missing_domains': list(readiness.missing_domains),
            'safe_user_message': readiness.safe_user_message,
            'next_supported_actions': list(readiness.next_supported_actions),
            'partial_evidence_present': readiness.partial_evidence_present,
        },
    }
