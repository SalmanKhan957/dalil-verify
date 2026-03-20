from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app

FIXTURE_PATH = Path('tests/fixtures/verifier_regression_cases.json')
DEFAULT_CASE_IDS = [
    'single_ayah_94_5',
    'short_passage_112_1_4',
    'long_passage_23_1_6',
    'long_passage_1_1_7',
    'online_mushaf_8_1_5',
]


def load_cases() -> list[dict]:
    with FIXTURE_PATH.open('r', encoding='utf-8') as f:
        return json.load(f)


def iter_selected_cases(all_cases: list[dict], selected_ids: set[str] | None) -> list[dict]:
    if not selected_ids:
        selected_ids = set(DEFAULT_CASE_IDS)
    return [case for case in all_cases if case['id'] in selected_ids]


def main() -> int:
    parser = argparse.ArgumentParser(description='Run a small verifier performance smoke benchmark.')
    parser.add_argument('--case-id', action='append', dest='case_ids', default=[], help='Specific regression case id to benchmark. Repeatable.')
    parser.add_argument('--iterations', type=int, default=3, help='How many timed iterations to run per case.')
    parser.add_argument('--fail-over-ms', type=float, default=8000.0, help='Fail if any case median exceeds this threshold.')
    args = parser.parse_args()

    cases = iter_selected_cases(load_cases(), set(args.case_ids) if args.case_ids else None)
    if not cases:
        raise SystemExit('No matching regression cases found for performance smoke run.')

    failures: list[str] = []

    with TestClient(app) as client:
        print(f'Running {len(cases)} verifier performance smoke case(s) x {args.iterations} iteration(s) each.\n')
        for case in cases:
            timings_ms: list[float] = []
            for _ in range(args.iterations):
                start = time.perf_counter()
                response = client.post('/verify/quran', json={'text': case['query']})
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                timings_ms.append(elapsed_ms)
                if response.status_code != case.get('expected_status_code', 200):
                    failures.append(f"{case['id']}: unexpected status code {response.status_code}")
                    break

            median_ms = statistics.median(timings_ms)
            p95_like_ms = max(timings_ms)
            print(f"- {case['id']}: median={median_ms:.1f}ms max={p95_like_ms:.1f}ms")
            if median_ms > args.fail_over_ms:
                failures.append(
                    f"{case['id']}: median latency {median_ms:.1f}ms exceeded threshold {args.fail_over_ms:.1f}ms"
                )

    if failures:
        print('\nFailures:')
        for item in failures:
            print(f'  * {item}')
        return 1

    print('\nPerformance smoke run completed without threshold failures.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
