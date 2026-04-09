from __future__ import annotations

from dataclasses import dataclass, field


# Canonical names moving forward
@dataclass(slots=True)
class JudgedHadithQuery:
    query_text: str
    expected_topics: tuple[str, ...] = ()
    expected_profile: str = 'general_topic'
    acceptable_refs: tuple[str, ...] = ()
    bad_refs: tuple[str, ...] = ()
    notes: str = ''


@dataclass(slots=True)
class HadithEvalResult:
    query_text: str
    top_ref: str | None = None
    top_topics: tuple[str, ...] = ()
    matched: bool = False
    warnings: tuple[str, ...] = ()
    debug: dict[str, object] = field(default_factory=dict)


# Backward-compatible aliases for previously shipped scaffold/tests
HadithTopicalJudgment = JudgedHadithQuery
HadithTopicalEvalResult = HadithEvalResult

__all__ = [
    'JudgedHadithQuery',
    'HadithEvalResult',
    'HadithTopicalJudgment',
    'HadithTopicalEvalResult',
]
