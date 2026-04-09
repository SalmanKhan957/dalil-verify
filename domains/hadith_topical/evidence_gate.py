from __future__ import annotations

from domains.hadith_topical.contracts import HadithTopicalCandidate, HadithTopicalQuery, HadithTopicalResult


def passes_topical_evidence_gate(
    candidate: HadithTopicalCandidate,
    *,
    query: HadithTopicalQuery | None = None,
    minimum_centrality: float = 0.42,
    minimum_answerability: float = 0.48,
    maximum_incidental_penalty: float = 0.45,
    maximum_narrative_specificity: float = 0.78,
) -> bool:
    centrality = float(candidate.central_topic_score or 0.0)
    answerability = float(candidate.answerability_score if candidate.answerability_score is not None else (candidate.central_topic_score or 0.0))
    incidental_penalty = float(candidate.incidental_topic_penalty or 0.0)
    narrative_specificity = float(candidate.narrative_specificity_score or 0.0)
    if centrality < minimum_centrality:
        return False
    if answerability < minimum_answerability:
        return False
    if incidental_penalty > maximum_incidental_penalty:
        return False
    if query is not None and query.query_profile == 'general_topic' and narrative_specificity > maximum_narrative_specificity:
        return False
    return True


def gate_topical_result(query: HadithTopicalQuery | HadithTopicalResult, result: HadithTopicalResult | None = None) -> HadithTopicalResult:
    if result is None:
        result = query
        query = None
    if result.abstain:
        return result
    surviving = tuple(candidate for candidate in result.selected if passes_topical_evidence_gate(candidate, query=query))
    if surviving:
        return HadithTopicalResult(selected=surviving, abstain=False, warnings=result.warnings, debug=result.debug)
    warnings = tuple(dict.fromkeys((*result.warnings, 'all_candidates_failed_evidence_gate')))
    return HadithTopicalResult(selected=(), abstain=True, abstain_reason='topical_evidence_gate_failed', warnings=warnings, debug=result.debug)
