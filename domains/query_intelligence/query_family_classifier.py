from __future__ import annotations

import re
from difflib import SequenceMatcher

from domains.query_intelligence.catalog import load_query_family_definitions
from domains.query_intelligence.models import QueryFamilyMatch
from domains.query_intelligence.normalization import normalize_user_query

_TOKEN_RE = re.compile(r"[A-Za-z']+")


def _tokens(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(text or '')}


def classify_query_family(query: str) -> QueryFamilyMatch | None:
    normalized = normalize_user_query(query).casefold()
    if not normalized:
        return None
    query_tokens = _tokens(normalized)
    best: QueryFamilyMatch | None = None
    best_score = 0.0
    for family in load_query_family_definitions():
        matched_cues: list[str] = []
        matched_anti_cues: list[str] = []
        score = 0.0
        for cue in family.cue_phrases:
            if cue in normalized:
                matched_cues.append(cue)
                score = max(score, 0.82)
        for anti_cue in family.anti_cues:
            if anti_cue and anti_cue in normalized:
                matched_anti_cues.append(anti_cue)
        cue_overlap = len(query_tokens & set(family.domain_cues))
        if cue_overlap < family.minimum_domain_cue_overlap and not matched_cues:
            continue
        if not matched_cues and cue_overlap:
            for example in family.example_queries:
                similarity = SequenceMatcher(a=normalized, b=normalize_user_query(example).casefold()).ratio()
                if similarity >= 0.72:
                    score = max(score, round(0.55 + (0.3 * similarity), 3))
        if cue_overlap:
            score += min(0.12, 0.04 * cue_overlap)
        if family.domain == 'hadith' and 'prophet ﷺ' in normalized:
            score += 0.04
        if matched_anti_cues:
            score -= min(0.4, 0.16 * len(matched_anti_cues))
        if score < 0.45:
            continue
        score = min(0.99, max(0.0, score))
        candidate = QueryFamilyMatch(
            family_id=family.family_id,
            domain=family.domain,
            route_type=family.route_type,
            query_profile=family.query_profile,
            confidence=round(score, 3),
            public_supported=family.public_supported,
            needs_clarification=family.needs_clarification,
            matched_cues=tuple(matched_cues),
            debug={
                'normalized_query': normalized,
                'matched_cues': matched_cues,
                'matched_anti_cues': matched_anti_cues,
                'cue_overlap': cue_overlap,
                'priority': family.priority,
            },
        )
        weighted = score + (family.priority / 1000.0)
        if weighted > best_score:
            best = candidate
            best_score = weighted
    return best
