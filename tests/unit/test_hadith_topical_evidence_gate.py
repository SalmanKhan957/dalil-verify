from domains.hadith_topical.contracts import HadithTopicalCandidate, HadithTopicalResult
from domains.hadith_topical.evidence_gate import gate_topical_result, passes_topical_evidence_gate


def test_evidence_gate_passes_strong_candidate() -> None:
    candidate = HadithTopicalCandidate(
        canonical_ref='hadith:1',
        source_id='hadith:sahih-al-bukhari-en',
        retrieval_origin='hybrid',
        central_topic_score=0.8,
        incidental_topic_penalty=0.1,
    )
    assert passes_topical_evidence_gate(candidate)


def test_evidence_gate_abstains_when_only_candidates_fail() -> None:
    candidate = HadithTopicalCandidate(
        canonical_ref='hadith:1',
        source_id='hadith:sahih-al-bukhari-en',
        retrieval_origin='hybrid',
        central_topic_score=0.2,
        incidental_topic_penalty=0.8,
    )
    result = HadithTopicalResult(selected=(candidate,), abstain=False)
    gated = gate_topical_result(result)
    assert gated.abstain
