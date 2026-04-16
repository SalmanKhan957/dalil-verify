from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.ask.planner_types import AskPlan, ResponseMode, TerminalState


@dataclass(frozen=True, slots=True)
class EvidenceReadiness:
    answerable: bool
    llm_ready: bool
    force_abstain: bool
    reason_code: str | None
    missing_domains: tuple[str, ...]
    safe_user_message: str | None
    next_supported_actions: tuple[str, ...] = ()
    partial_evidence_present: bool = False


_QURAN_TEXT_ACTIONS = (
    'Ask for the Quran text only',
    'Try a direct Quran reference such as 2:255',
)
_QURAN_EXPLAIN_ACTIONS = (
    'Try a direct Quran reference such as 2:255',
    'Ask for the verse text only',
)
_HADITH_ACTIONS = (
    'Use a direct hadith citation such as Bukhari 20',
    'Try a different explicit hadith reference',
)
_GENERIC_ACTIONS = (
    'Ask a direct Quran reference such as 2:255',
    'Ask a direct hadith reference such as Bukhari 20',
)


def _answered_like_terminal_state(plan: AskPlan) -> bool:
    terminal_state = getattr(plan, 'terminal_state', None)
    if terminal_state is None:
        return not plan.should_abstain and plan.response_mode not in {ResponseMode.ABSTAIN, ResponseMode.CLARIFY}
    terminal_value = terminal_state.value if hasattr(terminal_state, 'value') else str(terminal_state)
    return terminal_value == TerminalState.ANSWERED.value


def _quran_available(quran_support: dict[str, Any] | None, verifier_result: dict[str, Any] | None) -> bool:
    if quran_support is not None:
        return True
    return bool((verifier_result or {}).get('best_match'))


def assess_evidence_readiness(
    *,
    plan: AskPlan,
    quran_support: dict[str, Any] | None,
    hadith_support: dict[str, Any] | None,
    tafsir_support: list[dict[str, Any]],
    verifier_result: dict[str, Any] | None = None,
) -> EvidenceReadiness:
    """Central trust gate for answer composition.

    Current DALIL policy: if the request would otherwise be answered but the required
    source evidence for that response mode is not present, the surface must degrade to
    an honest abstain rather than a polished synthetic answer.
    """

    if plan.response_mode in {ResponseMode.ABSTAIN, ResponseMode.CLARIFY}:
        return EvidenceReadiness(
            answerable=False,
            llm_ready=False,
            force_abstain=False,
            reason_code=None,
            missing_domains=(),
            safe_user_message=None,
        )

    if not _answered_like_terminal_state(plan) or bool(getattr(plan, 'followup_rejected', False)):
        return EvidenceReadiness(
            answerable=False,
            llm_ready=False,
            force_abstain=False,
            reason_code=None,
            missing_domains=(),
            safe_user_message=None,
        )

    quran_available = _quran_available(quran_support, verifier_result)
    hadith_available = hadith_support is not None
    tafsir_available = bool(tafsir_support)
    partial_evidence_present = any((quran_available, hadith_available, tafsir_available))

    missing_domains: list[str] = []
    safe_user_message: str | None = None
    next_supported_actions: tuple[str, ...] = ()

    mode = plan.response_mode
    if mode == ResponseMode.VERIFICATION_ONLY:
        answerable = quran_available
        if not answerable:
            missing_domains = ['quran']
            safe_user_message = 'I could not verify that against a reliable Quran match, so I should not answer as if the verse was confirmed.'
            next_supported_actions = _QURAN_TEXT_ACTIONS
    elif mode in {ResponseMode.QURAN_TEXT, ResponseMode.QURAN_EXPLANATION}:
        answerable = quran_available
        if not answerable:
            missing_domains = ['quran']
            safe_user_message = 'I could not retrieve enough Quran evidence for that request, so I should not answer it as if the verse was reliably resolved.'
            next_supported_actions = _QURAN_EXPLAIN_ACTIONS if mode == ResponseMode.QURAN_EXPLANATION else _QURAN_TEXT_ACTIONS
    elif mode in {ResponseMode.QURAN_WITH_TAFSIR, ResponseMode.VERIFICATION_THEN_EXPLAIN}:
        answerable = quran_available and tafsir_available
        if not answerable:
            if not quran_available:
                missing_domains.append('quran')
            if not tafsir_available:
                missing_domains.append('tafsir')
            if quran_available and not tafsir_available:
                safe_user_message = 'I found the Quran passage, but I do not have enough approved tafsir evidence to explain it reliably.'
            else:
                safe_user_message = 'I could not retrieve enough Quran and tafsir evidence to explain that reliably.'
            next_supported_actions = _QURAN_EXPLAIN_ACTIONS
    elif mode in {ResponseMode.HADITH_TEXT, ResponseMode.HADITH_EXPLANATION, ResponseMode.TOPICAL_HADITH}:
        answerable = hadith_available
        if not answerable:
            missing_domains = ['hadith']
            safe_user_message = 'I could not retrieve enough approved hadith evidence for that request, so I should not answer it as if the narration was reliably grounded.'
            next_supported_actions = _HADITH_ACTIONS
    elif mode == ResponseMode.TOPICAL_TAFSIR:
        answerable = tafsir_available
        if not answerable:
            missing_domains = ['tafsir']
            safe_user_message = 'I could not retrieve enough approved tafsir evidence for that request, so I should not present a topical explanation from thin air.'
            next_supported_actions = _QURAN_EXPLAIN_ACTIONS
    elif mode == ResponseMode.TOPICAL_MULTI_SOURCE:
        answerable = tafsir_available or hadith_available
        if not answerable:
            missing_domains = ['tafsir', 'hadith']
            safe_user_message = 'I could not retrieve enough approved source evidence for that request, so I should not synthesize a multi-source answer.'
            next_supported_actions = _GENERIC_ACTIONS
    else:
        answerable = True

    return EvidenceReadiness(
        answerable=answerable,
        llm_ready=answerable,
        force_abstain=not answerable,
        reason_code='insufficient_evidence' if not answerable else None,
        missing_domains=tuple(missing_domains),
        safe_user_message=safe_user_message,
        next_supported_actions=next_supported_actions,
        partial_evidence_present=partial_evidence_present,
    )
