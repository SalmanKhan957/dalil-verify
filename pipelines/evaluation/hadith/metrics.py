from __future__ import annotations

from pipelines.evaluation.hadith.contracts import HadithEvalResult, JudgedHadithQuery


def score_eval_result(query: JudgedHadithQuery, result: HadithEvalResult) -> dict[str, float | bool]:
    top1_ok = bool(result.top_ref and (not query.acceptable_refs or result.top_ref in query.acceptable_refs))
    bad_hit = bool(result.top_ref and result.top_ref in query.bad_refs)
    topic_overlap = bool(set(query.expected_topics) & set(result.top_topics))
    return {
        'top1_ok': top1_ok,
        'bad_hit': bad_hit,
        'topic_overlap': topic_overlap,
        'passed': bool((top1_ok or topic_overlap) and not bad_hit),
    }
