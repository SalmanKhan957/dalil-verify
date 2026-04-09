from __future__ import annotations

from domains.hadith_topical.contracts import HadithTopicalCandidate, HadithTopicalQuery, HadithTopicalResult


def _normalize_rank_signal(score: float | None) -> float:
    value = float(score or 0.0)
    if value <= 0.0:
        return 0.0
    if value <= 1.0:
        return value
    return value / (value + 4.0)


def _normalized_role(role: str | None) -> str:
    value = str(role or '').strip() or 'narrative_incident'
    if value == 'narrative_context':
        return 'narrative_incident'
    return value


def _retrieval_family(query: HadithTopicalQuery) -> str:
    return str((query.debug or {}).get('retrieval_family') or query.query_profile or 'general_topic')


def _preferred_role_bonus(query: HadithTopicalQuery, candidate: HadithTopicalCandidate) -> float:
    role = _normalized_role(candidate.guidance_role)
    family = _retrieval_family(query)
    if family == 'entity_eschatology':
        if role == 'thematic_passage':
            return 0.14
        if role == 'narrative_incident':
            return 0.06
        return -0.02
    if family == 'narrative_event':
        if role in {'thematic_passage', 'narrative_incident'}:
            return 0.1
        return 0.0
    if family == 'ritual_practice':
        if role in {'thematic_passage', 'legal_specific_case', 'narrative_incident'}:
            return 0.1
        return 0.0
    if query.query_profile == 'prophetic_guidance':
        if role in {'direct_moral_instruction', 'virtue_statement', 'warning'}:
            return 0.12
        if role == 'narrative_incident':
            return -0.08
    if query.query_profile == 'warning':
        if role in {'warning', 'direct_moral_instruction'}:
            return 0.1
        if role == 'narrative_incident':
            return -0.06
    if query.query_profile == 'virtue':
        if role == 'virtue_statement':
            return 0.1
        if role == 'narrative_incident':
            return -0.06
    if query.query_profile == 'guidance':
        if role in {'direct_moral_instruction', 'virtue_statement', 'warning'}:
            return 0.06
        if role == 'narrative_incident':
            return -0.04
    return 0.0


def _builder_rank(candidate: HadithTopicalCandidate) -> float:
    return max(0.0, min(float((candidate.metadata or {}).get('builder_rank_score') or 0.0), 1.0))


def _candidate_score(candidate: HadithTopicalCandidate, query: HadithTopicalQuery) -> float:
    lexical = _normalize_rank_signal(candidate.fusion_score if candidate.fusion_score is not None else candidate.lexical_score)
    semantic = _normalize_rank_signal(candidate.rerank_score if candidate.rerank_score is not None else candidate.vector_score)
    centrality = float(candidate.central_topic_score or 0.0)
    answerability = float(candidate.answerability_score or 0.0)
    incidental = float(candidate.incidental_topic_penalty or 0.0)
    narrative_specificity = float(candidate.narrative_specificity_score or 0.0)
    topic_alignment = 0.08 if (set(candidate.matched_topics or ()) & set(query.topic_candidates or ())) else 0.0
    family = _retrieval_family(query)
    if family in {'entity_eschatology', 'narrative_event', 'ritual_practice'}:
        return (
            0.2 * lexical
            + 0.18 * semantic
            + 0.28 * centrality
            + 0.2 * answerability
            + 0.04 * _builder_rank(candidate)
            + topic_alignment
            + _preferred_role_bonus(query, candidate)
            - 0.06 * incidental
            - 0.02 * narrative_specificity
        )
    return (
        0.16 * lexical
        + 0.18 * semantic
        + 0.26 * centrality
        + 0.22 * answerability
        + 0.08 * _builder_rank(candidate)
        + topic_alignment
        + _preferred_role_bonus(query, candidate)
        - 0.1 * incidental
        - 0.04 * narrative_specificity
    )


def _thresholds_for_query(query: HadithTopicalQuery) -> tuple[float, float, float]:
    family = _retrieval_family(query)
    if family == 'entity_eschatology':
        return (0.46, 0.42, 0.5)
    if family == 'narrative_event':
        return (0.44, 0.38, 0.46)
    if family == 'ritual_practice':
        return (0.48, 0.4, 0.48)
    if not query.topic_candidates:
        return (0.7, 0.56, 0.62)
    if query.query_profile == 'prophetic_guidance':
        return (0.64, 0.58, 0.62)
    if query.query_profile in {'warning', 'virtue', 'guidance'}:
        return (0.61, 0.55, 0.58)
    return (0.58, 0.42, 0.48)


def select_topical_candidates(
    query: HadithTopicalQuery,
    candidates: list[HadithTopicalCandidate],
    *,
    max_results: int = 5,
) -> HadithTopicalResult:
    minimum_score, minimum_centrality, minimum_answerability = _thresholds_for_query(query)
    ranked = sorted(
        candidates,
        key=lambda item: (
            -_candidate_score(item, query),
            -float(item.central_topic_score or 0.0),
            -float(item.answerability_score or 0.0),
            -float(item.rerank_score or 0.0),
            float(item.incidental_topic_penalty or 0.0),
            float(item.narrative_specificity_score or 0.0),
            item.canonical_ref,
        ),
    )
    selected = []
    selected_refs: set[str] = set()
    rejected: list[dict[str, object]] = []
    family = _retrieval_family(query)
    for candidate in ranked:
        score = _candidate_score(candidate, query)
        centrality = float(candidate.central_topic_score or 0.0)
        answerability = float(candidate.answerability_score or 0.0)
        role = _normalized_role(candidate.guidance_role)
        has_topic_alignment = bool(set(candidate.matched_topics or ()) & set(query.topic_candidates)) if query.topic_candidates else False
        if candidate.canonical_ref in selected_refs:
            rejected.append({'canonical_ref': candidate.canonical_ref, 'reason': 'duplicate_parent_ref'})
            continue
        if family not in {'entity_eschatology', 'narrative_event', 'ritual_practice'}:
            if query.topic_candidates and not has_topic_alignment:
                rerank = float(candidate.rerank_score or 0.0)
                builder_rank = _builder_rank(candidate)
                if centrality < 0.9 or answerability < 0.86 or (rerank < 0.7 and builder_rank < 0.75):
                    rejected.append({'canonical_ref': candidate.canonical_ref, 'reason': 'topic_alignment_missing'})
                    continue
            if query.query_profile in {'prophetic_guidance', 'guidance', 'warning', 'virtue'} and role == 'narrative_incident':
                if (centrality < 0.8 or answerability < 0.8 or not has_topic_alignment):
                    rejected.append({'canonical_ref': candidate.canonical_ref, 'reason': 'narrative_not_direct_enough'})
                    continue
            if not query.topic_candidates and role == 'narrative_incident':
                rejected.append({'canonical_ref': candidate.canonical_ref, 'reason': 'broad_query_requires_direct_guidance'})
                continue
        else:
            if family == 'entity_eschatology' and not ((candidate.metadata or {}).get('thematic_passage') or has_topic_alignment):
                rejected.append({'canonical_ref': candidate.canonical_ref, 'reason': 'entity_family_requires_thematic_passage'})
                continue
        if score < minimum_score:
            rejected.append({'canonical_ref': candidate.canonical_ref, 'reason': 'score_below_threshold', 'score': round(score, 3)})
            continue
        if centrality < minimum_centrality:
            rejected.append({'canonical_ref': candidate.canonical_ref, 'reason': 'centrality_below_threshold', 'centrality': round(centrality, 3)})
            continue
        if answerability < minimum_answerability:
            rejected.append({'canonical_ref': candidate.canonical_ref, 'reason': 'answerability_below_threshold', 'answerability': round(answerability, 3)})
            continue
        selected.append(candidate)
        selected_refs.add(candidate.canonical_ref)
        if len(selected) >= max(1, int(max_results)):
            break
    debug = {
        'selection_thresholds': {
            'minimum_score': minimum_score,
            'minimum_centrality': minimum_centrality,
            'minimum_answerability': minimum_answerability,
            'retrieval_family': family,
        },
        'ranked_candidates': [
            {
                'canonical_ref': candidate.canonical_ref,
                'composite_score': round(_candidate_score(candidate, query), 3),
                'rerank_score': round(float(candidate.rerank_score or 0.0), 3),
                'central_topic_score': round(float(candidate.central_topic_score or 0.0), 3),
                'answerability_score': round(float(candidate.answerability_score or 0.0), 3),
                'incidental_topic_penalty': round(float(candidate.incidental_topic_penalty or 0.0), 3),
                'guidance_role': _normalized_role(candidate.guidance_role),
                'matched_topics': list(candidate.matched_topics or ()),
            }
            for candidate in ranked[:10]
        ],
        'rejected_candidates': rejected[:10],
    }
    if not selected:
        return HadithTopicalResult(selected=(), abstain=True, abstain_reason='insufficient_ranked_evidence', warnings=('no_ranked_candidate_passed_thresholds',), debug=debug)
    warnings = ('additional_hadith_matches_available',) if len(ranked) > len(selected) else ()
    return HadithTopicalResult(selected=tuple(selected), abstain=False, warnings=warnings, debug=debug)
