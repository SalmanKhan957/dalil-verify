from __future__ import annotations

import re

from domains.hadith_topical.contracts import HadithTopicalCandidate, HadithTopicalQuery, HadithTopicalResult


# ---------------------------------------------------------------------------
# Query-shape detection (Phase 3.1)
#
# The upstream resolver already picks the right leaf topic; this classifier
# picks the right *shape* of hadith within that topic. Example: for the query
# "how did the prophet do ghusl?", the resolver correctly lands on
# ritual.tahara.ghusl_bathing. But within that topic, Bukhari contains:
#   - a ruling ("Friday ghusl is compulsory")        [direct_moral_instruction]
#   - procedural descriptions ("he poured water thrice on his head")  [narrative_incident]
#   - legal Q&A ("does a woman need ghusl after a wet dream?") [direct_moral_instruction]
# For a "how" query, the procedural narrative is the best answer. For a
# "what did he say" query, the direct teaching is best.
# ---------------------------------------------------------------------------

_HOW_DESCRIBE_PATTERNS = (
    r'\bhow\b',
    r'\bdescribe\b',
    r'\bdescription\b',
    r'\bmethod\b',
    r'\bway\b',
    r'\bprocedure\b',
    r'\bshow me\b',
    r'\bwhat is it like\b',
)
_PROPHETIC_TEACHING_PATTERNS = (
    r"\bwhat did the prophet\s+(?:say|teach|advise|command)\b",
    r"\bwhat does the prophet\s+(?:say|teach)\b",
    r"\bwhat did the messenger\s+(?:say|teach)\b",
    r"\bdid the prophet\s+(?:say|teach|advise|warn|command|mention)\b",
    r"\bprophet'?s\s+(?:teaching|guidance|advice|command)\b",
    r"\baccording to the prophet\b",
)
_WARNING_RULING_PATTERNS = (
    r'\bpunishment\b',
    r'\bforbid\b',
    r'\bforbidden\b',
    r'\bharam\b',
    r'\bprohibit',
    r'\brulings?\b',
    r'\bwarn',
    r'\bsin\b',
    r'\bpenalty\b',
    r'\bis it (haram|allowed|permissible)\b',
)
_VIRTUE_PATTERNS = (
    r'\bvirtues?\b',
    r'\bmerits?\b',
    r'\breward\b',
    r'\bblessings?\b',
    r'\bbenefit',
    r'\bexcellenc',
)


def _compile(patterns: tuple[str, ...]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_HOW_RE = _compile(_HOW_DESCRIBE_PATTERNS)
_PROPHETIC_RE = _compile(_PROPHETIC_TEACHING_PATTERNS)
_WARNING_RE = _compile(_WARNING_RULING_PATTERNS)
_VIRTUE_RE = _compile(_VIRTUE_PATTERNS)


def detect_query_shape(query: HadithTopicalQuery) -> str:
    """Classify the query's *shape* (separate from its topic / family).

    Shapes drive per-role bonuses in `_shape_role_bonus`. Order matters:
    most specific shape first. Broad queries fall through to 'broad'.

    Uses raw_query FIRST because the Bukhari topical normalizer strips
    shape-signal words ("how", "what did", "describe") as conversational
    fluff. By the time the query reaches normalized_query, the shape is
    lost — we need the original wording.
    """
    text = (query.raw_query or query.normalized_query or '').lower()
    if not text:
        return 'broad'
    if any(p.search(text) for p in _HOW_RE):
        return 'procedural_descriptive'
    if any(p.search(text) for p in _PROPHETIC_RE):
        return 'prophetic_teaching'
    if any(p.search(text) for p in _WARNING_RE):
        return 'ruling_warning'
    if any(p.search(text) for p in _VIRTUE_RE):
        return 'virtue'
    return 'broad'


def _shape_role_bonus(query: HadithTopicalQuery, candidate: HadithTopicalCandidate) -> float:
    """Additive bonus on top of `_preferred_role_bonus` for query-shape fit.

    Weights sized so they can flip the primary candidate among topically-tied
    records (all at central_topic_score=0.9) without overpowering the base
    retrieval signal.
    """
    shape = detect_query_shape(query)
    if shape == 'broad':
        return 0.0
    role = _normalized_role(candidate.guidance_role)

    if shape == 'procedural_descriptive':
        # "How did the prophet do X?" — Aisha-style descriptive narrations are gold.
        if role == 'narrative_incident':
            return 0.14
        if role == 'direct_moral_instruction':
            return 0.04
        if role in {'warning', 'virtue_statement'}:
            return -0.04
        return 0.0

    if shape == 'prophetic_teaching':
        # "What did the prophet say about X?" — canonical teachings first.
        if role == 'direct_moral_instruction':
            return 0.14
        if role in {'virtue_statement', 'warning'}:
            return 0.06
        if role == 'narrative_incident':
            return -0.04
        return 0.0

    if shape == 'ruling_warning':
        if role == 'warning':
            return 0.14
        if role == 'direct_moral_instruction':
            return 0.08
        if role == 'narrative_incident':
            return -0.02
        return 0.0

    if shape == 'virtue':
        if role == 'virtue_statement':
            return 0.14
        if role == 'direct_moral_instruction':
            return 0.06
        if role == 'narrative_incident':
            return -0.02
        return 0.0

    return 0.0


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
    # Shape-override: when the query shape is procedural/descriptive, the
    # classifier's query_profile (often 'prophetic_guidance' because "prophet"
    # is in the query) is misleading — we WANT narrative_incident records
    # and MUST NOT apply its anti-narrative penalty. Return 0 here; the
    # separate _shape_role_bonus carries the correct procedural signal.
    shape = detect_query_shape(query)
    if shape == 'procedural_descriptive':
        return 0.0
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
    shape_bonus = _shape_role_bonus(query, candidate)
    if family in {'entity_eschatology', 'narrative_event', 'ritual_practice'}:
        return (
            0.2 * lexical
            + 0.18 * semantic
            + 0.28 * centrality
            + 0.2 * answerability
            + 0.04 * _builder_rank(candidate)
            + topic_alignment
            + _preferred_role_bonus(query, candidate)
            + shape_bonus
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
        + shape_bonus
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
