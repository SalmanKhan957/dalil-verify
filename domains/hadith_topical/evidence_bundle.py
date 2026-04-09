from __future__ import annotations

from typing import Any

from domains.hadith_topical.contracts import HadithTopicalCandidate, HadithTopicalQuery


def _truncate(text: str | None, *, limit: int = 280) -> str | None:
    value = str(text or '').strip()
    if not value:
        return None
    return value[:limit].rstrip() + ('…' if len(value) > limit else '')


def build_topical_evidence_bundle(
    query: HadithTopicalQuery,
    candidates: list[HadithTopicalCandidate],
    *,
    max_items: int = 5,
) -> dict[str, Any]:
    evidence_units = []
    supporting_refs: list[str] = []
    seen_refs: set[str] = set()
    seen_units: set[tuple[str, str]] = set()
    for candidate in candidates[: max(1, int(max_items))]:
        metadata = dict(candidate.metadata or {})
        guidance_unit_id = str(metadata.get('guidance_unit_id') or '')
        unit_key = (candidate.canonical_ref, guidance_unit_id)
        if unit_key in seen_units:
            continue
        seen_units.add(unit_key)
        if candidate.canonical_ref not in seen_refs:
            supporting_refs.append(candidate.canonical_ref)
            seen_refs.add(candidate.canonical_ref)
        evidence_units.append(
            {
                'canonical_ref': candidate.canonical_ref,
                'source_id': candidate.source_id,
                'retrieval_origin': candidate.retrieval_origin,
                'guidance_unit_id': metadata.get('guidance_unit_id'),
                'guidance_role': candidate.guidance_role,
                'topic_family': candidate.topic_family,
                'matched_topics': list(candidate.matched_topics or ()),
                'matched_terms': list(candidate.matched_terms or ()),
                'central_topic_score': candidate.central_topic_score,
                'answerability_score': candidate.answerability_score,
                'fusion_score': candidate.fusion_score,
                'rerank_score': candidate.rerank_score,
                'lexical_score': candidate.lexical_score,
                'vector_score': candidate.vector_score,
                'contextual_summary': _truncate(metadata.get('contextual_summary') or metadata.get('summary_text') or metadata.get('snippet') or metadata.get('english_text')),
                'source_excerpt': _truncate(metadata.get('span_text') or metadata.get('english_text') or metadata.get('snippet'), limit=480),
            }
        )
    return {
        'bundle_version': 'hadith_topical_llm.v2',
        'query': query.raw_query,
        'normalized_query': query.normalized_query,
        'query_profile': query.query_profile,
        'topic_candidates': list(query.topic_candidates),
        'topic_family': query.topic_family,
        'directive_biases': list(query.directive_biases),
        'supporting_refs': supporting_refs,
        'candidate_count': len(evidence_units),
        'evidence_units': evidence_units,
    }


def build_llm_composition_contract(bundle: dict[str, Any]) -> dict[str, Any]:
    evidence_units = bundle.get('evidence_units') or []
    evidence_lines = []
    for idx, item in enumerate(evidence_units, start=1):
        guidance_unit = item.get('guidance_unit_id') or '-'
        evidence_lines.append(
            f"{idx}. {item.get('canonical_ref')} | unit={guidance_unit} | role={item.get('guidance_role')} | "
            f"topics={','.join(item.get('matched_topics') or []) or '-'} | "
            f"summary={item.get('contextual_summary') or ''}"
        )
    system_prompt = (
        'You are composing a bounded hadith answer for DALIL. Use only the supplied hadith evidence units. '
        'Do not introduce Quran, tafsir, fiqh rulings, or unsupported synthesis. Prefer direct prophetic guidance '
        'over incidental narrative context. If the evidence is weak, overlapping, or non-direct, say so clearly.'
    )
    user_prompt = (
        f"Query: {bundle.get('query')}\n"
        f"Normalized query: {bundle.get('normalized_query')}\n"
        f"Query profile: {bundle.get('query_profile')}\n"
        f"Topic candidates: {', '.join(bundle.get('topic_candidates') or []) or 'none'}\n\n"
        'Approved hadith evidence units:\n' + '\n'.join(evidence_lines)
    )
    return {
        'contract_version': 'hadith_topical_llm.v2',
        'system_prompt': system_prompt,
        'user_prompt': user_prompt,
        'supporting_refs': list(bundle.get('supporting_refs') or []),
        'evidence_unit_count': len(evidence_units),
        'source_domain': 'hadith',
        'composition_scope': 'bounded_single_domain',
    }
