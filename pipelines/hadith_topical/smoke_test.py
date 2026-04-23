"""Bukhari topical retrieval smoke test — canonical query battery.

Runs a fixed battery of ~30 canonical queries end-to-end through
HadithTopicalSearchService against the live OpenSearch index. For each
case, asserts one of:

    PASS: the top selected candidate's primary_topics contains the expected slug
    PASS: the expected slug is `None` (intentionally broad query) and the
          service produced at least one candidate
    FAIL: the top candidate's primary_topics does not contain the expected slug
    FAIL: the service abstained when a topical result was expected

Exit code 0 iff all cases pass. Non-zero otherwise — suitable for CI.

Usage:
    python -m pipelines.hadith_topical.smoke_test
    python -m pipelines.hadith_topical.smoke_test --verbose
    python -m pipelines.hadith_topical.smoke_test --json

Preconditions:
    - DATABASE_URL and OPENSEARCH_URL env vars set
    - v2 index built and aliased (see build_bukhari_topical_v2_index + cutover_alias)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from domains.hadith_topical.search_service import HadithTopicalSearchService

log = logging.getLogger('smoke_test')


@dataclass(frozen=True, slots=True)
class Case:
    query: str
    expected_primary: str | None  # None = accept any primary, just not abstain
    allow_alternatives: tuple[str, ...] = ()


CANONICAL_CASES: tuple[Case, ...] = (
    # ── Core documented bug cases ───────────────────────────────────────
    Case('What did the prophet say about zina?', 'fiqh.hudood.zina_adultery'),
    Case('what did the prophet say about adultery', 'fiqh.hudood.zina_adultery'),
    Case('punishment of adultery', 'fiqh.hudood.zina_adultery'),
    Case('What did the prophet say about Dajjal?', 'eschatology.dajjal'),
    Case('did the prophet mention the antichrist', 'eschatology.dajjal'),
    Case('rulings on riba', 'fiqh.business.riba_usury'),
    Case('what is usury in islam', 'fiqh.business.riba_usury'),
    # Narrator-leak regression: Abraham hadiths must NOT get pulled by zina
    Case('hadiths about abraham and circumcision', 'historical.prophets.ibrahim'),

    # ── Ritual / tahara ─────────────────────────────────────────────────
    Case('how did the prophet do ghusl?', 'ritual.tahara.ghusl_bathing'),
    Case('how to do wudu', 'ritual.tahara.wudu_ablution'),
    Case('fasting in ramadan', 'ritual.sawm.ramadan'),
    Case('Friday prayer rulings', 'ritual.salah.friday_jumua'),

    # ── Akhlaq ──────────────────────────────────────────────────────────
    Case('anger and self control', 'akhlaq.adab.anger_control'),
    Case('patience in hardship', 'akhlaq.adab.patience_sabr'),
    Case('backbiting', 'akhlaq.adab.backbiting_ghayba'),
    Case('envy and jealousy', 'akhlaq.adab.envy_hasad'),
    Case('duties to parents', 'akhlaq.adab.parents_duty'),

    # ── Eschatology ─────────────────────────────────────────────────────
    Case('virtues of paradise', 'eschatology.paradise_jannah'),
    Case('what about hellfire', 'eschatology.hellfire_jahannam'),
    Case('gog and magog', 'eschatology.gog_magog'),

    # ── Fiqh — hudud / justice / business ───────────────────────────────
    Case('punishment for theft', 'fiqh.hudood.theft_sariqa'),
    Case('blood money for a murder', 'fiqh.justice.blood_money_diyat'),

    # ── Historical ──────────────────────────────────────────────────────
    Case('virtues of abu bakr', 'historical.companions.abu_bakr'),
    Case('the battle of badr', 'historical.maghazi.badr'),

    # ── Foundational / aqeedah ──────────────────────────────────────────
    Case('what did the prophet say about intentions', 'foundational.intention_niyya'),
    Case('what is tawhid', 'aqeedah.tawhid.general'),
    Case('fitrah and innate faith', 'aqeedah.fitrah_innate_faith'),

    # ── Broad queries — accept any non-abstain ──────────────────────────
    Case('generosity and charity', None),
    Case('the merits of the companions', None),
)


@dataclass
class CaseResult:
    case: Case
    passed: bool
    reason: str
    top_ref: str | None = None
    top_primary: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0
    debug: dict[str, Any] = field(default_factory=dict)


def run_case(svc: HadithTopicalSearchService, case: Case) -> CaseResult:
    start = time.time()
    result = svc.search(
        raw_query=case.query,
        collection_source_id='hadith:bukhari',
        limit=5,
    )
    elapsed_ms = (time.time() - start) * 1000.0

    debug: dict[str, Any] = {
        'abstain_reason': result.abstain_reason,
        'warnings': list(result.warnings),
    }
    cg = result.debug.get('candidate_generation', {}) if isinstance(result.debug, dict) else {}
    tr = cg.get('topic_resolution', {}) if isinstance(cg, dict) else {}
    debug['resolved_primary'] = tr.get('primary_topic')
    debug['strict_bm25_hits'] = cg.get('strict_bm25_hits')
    debug['relaxed_bm25_hits'] = cg.get('relaxed_bm25_hits')
    debug['anchor_gate_applied'] = cg.get('anchor_gate_applied')

    top = result.selected[0] if result.selected else None
    if top is None:
        passed = case.expected_primary is None and False  # abstain never counts as pass
        return CaseResult(
            case=case,
            passed=False,
            reason='abstained' if case.expected_primary else 'abstained_on_broad_query',
            top_ref=None,
            top_primary=[],
            elapsed_ms=elapsed_ms,
            debug=debug,
        )

    top_primary = list(top.matched_topics or [])
    if case.expected_primary is None:
        return CaseResult(
            case=case, passed=True, reason='broad_ok',
            top_ref=top.canonical_ref, top_primary=top_primary,
            elapsed_ms=elapsed_ms, debug=debug,
        )
    acceptable = {case.expected_primary, *case.allow_alternatives}
    if acceptable & set(top_primary):
        return CaseResult(
            case=case, passed=True, reason='match',
            top_ref=top.canonical_ref, top_primary=top_primary,
            elapsed_ms=elapsed_ms, debug=debug,
        )
    return CaseResult(
        case=case, passed=False, reason='wrong_topic',
        top_ref=top.canonical_ref, top_primary=top_primary,
        elapsed_ms=elapsed_ms, debug=debug,
    )


def render_console(results: list[CaseResult], verbose: bool = False) -> None:
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    for r in results:
        mark = 'PASS' if r.passed else 'FAIL'
        expected = r.case.expected_primary or '(any)'
        top = r.top_ref or '(abstain)'
        primary = ','.join(r.top_primary[:2]) if r.top_primary else '(none)'
        print(f'[{mark}] {r.case.query[:50]:52s} -> {top:45s} {primary[:40]:42s}  {r.elapsed_ms:4.0f}ms  expected={expected}')
        if verbose and not r.passed:
            print(f'        reason={r.reason}  debug={r.debug}')
    print('')
    pct = 100 * passed / max(1, total)
    print(f'Summary: {passed}/{total} passed ({pct:.1f}%).')


def render_json(results: list[CaseResult]) -> str:
    payload = {
        'total': len(results),
        'passed': sum(1 for r in results if r.passed),
        'failed': sum(1 for r in results if not r.passed),
        'results': [
            {
                'query': r.case.query,
                'expected': r.case.expected_primary,
                'passed': r.passed,
                'reason': r.reason,
                'top_ref': r.top_ref,
                'top_primary_topics': r.top_primary,
                'elapsed_ms': round(r.elapsed_ms, 1),
                'debug': r.debug,
            }
            for r in results
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
    except Exception:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help='Show debug info on failures.')
    parser.add_argument('--json', action='store_true', help='Emit JSON results to stdout (for CI).')
    parser.add_argument('--only', default=None, help='Run only cases whose query contains this substring.')
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(message)s')

    cases: list[Case] = list(CANONICAL_CASES)
    if args.only:
        needle = args.only.lower()
        cases = [c for c in cases if needle in c.query.lower()]

    svc = HadithTopicalSearchService()
    results = [run_case(svc, case) for case in cases]

    if args.json:
        print(render_json(results))
    else:
        render_console(results, verbose=args.verbose)

    if any(not r.passed for r in results):
        sys.exit(1)


if __name__ == '__main__':
    main()
