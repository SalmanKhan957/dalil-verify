#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def token_count(text: str) -> int:
    return len((text or '').split())


def normalize_space(text: str) -> str:
    return ' '.join((text or '').split())


def clip_text(text: str, *, drop_left: int = 2, drop_right: int = 2, min_tokens: int = 4) -> str:
    toks = normalize_space(text).split()
    if len(toks) <= min_tokens + drop_left + drop_right:
        drop_left = min(drop_left, max(1, len(toks) // 5))
        drop_right = min(drop_right, max(1, len(toks) // 5))
    clipped = toks[drop_left: len(toks) - drop_right if drop_right else len(toks)]
    if len(clipped) < min_tokens:
        clipped = toks[max(0, 1): max(0, len(toks) - 1)]
    return ' '.join(clipped)


def mutate_middle_token(text: str, replacement: str = 'غلط') -> str:
    toks = normalize_space(text).split()
    if not toks:
        return replacement
    idx = len(toks) // 2
    toks[idx] = replacement
    return ' '.join(toks)


def rows_by_surah(ayah_rows: list[dict[str, str]]) -> dict[int, list[dict[str, str]]]:
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in ayah_rows:
        grouped[int(row['surah_no'])].append(row)
    for s in grouped:
        grouped[s] = sorted(grouped[s], key=lambda r: int(r['ayah_no']))
    return grouped


def citation_for_range(surah_no: int, start_ayah: int, end_ayah: int) -> str:
    if start_ayah == end_ayah:
        return f'Quran {surah_no}:{start_ayah}'
    return f'Quran {surah_no}:{start_ayah}-{end_ayah}'


def build_exact_span_text(grouped: dict[int, list[dict[str, str]]], *, span_len: int, min_tokens_required: int = 1, max_tokens_allowed: int | None = None, avoid_citation: str | None = None) -> tuple[str, str, dict[str, Any]]:
    best = None
    for surah_no, rows in grouped.items():
        for i in range(0, len(rows) - span_len + 1):
            block = rows[i:i + span_len]
            text = ' '.join(normalize_space(r['text_display']) for r in block)
            tc = token_count(text)
            citation = citation_for_range(surah_no, int(block[0]['ayah_no']), int(block[-1]['ayah_no']))
            if avoid_citation and citation == avoid_citation:
                continue
            if tc < min_tokens_required:
                continue
            if max_tokens_allowed is not None and tc > max_tokens_allowed:
                continue
            # prefer mid-sized spans with non-trivial token count
            score = (tc, span_len)
            if best is None or score > best[0]:
                best = (score, text, citation, {
                    'surah_no': surah_no,
                    'start_ayah': int(block[0]['ayah_no']),
                    'end_ayah': int(block[-1]['ayah_no']),
                    'token_count': tc,
                })
    if best is None:
        raise RuntimeError(f'Could not build a {span_len}-ayah exact span.')
    _, text, citation, meta = best
    return text, citation, meta


@dataclass
class TestCase:
    case_id: str
    category: str
    query: str
    expectation: str
    note: str
    expected_citation: str | None = None
    expected_canonical_unit: str | None = None
    extra: dict[str, Any] | None = None


def build_cases(repo_root: Path) -> list[TestCase]:
    data_dir = repo_root / 'data' / 'processed'
    ayah_csv = data_dir / 'quran' / 'quran_arabic_canonical.csv'
    passage_csv = data_dir / 'quran_passages' / 'quran_passage_windows_v1.csv'
    uthmani_csv = data_dir / 'quran_uthmani' / 'quran_arabic_uthmani_canonical.csv'

    ayah_rows = load_csv_rows(ayah_csv)
    passage_rows = load_csv_rows(passage_csv)
    uthmani_rows = load_csv_rows(uthmani_csv) if uthmani_csv.exists() else []

    grouped = rows_by_surah(ayah_rows)
    light_counts = Counter(row['text_normalized_light'] for row in ayah_rows)

    unique_ayah_rows = [r for r in ayah_rows if light_counts[r['text_normalized_light']] == 1]
    unique_ayah_rows.sort(key=lambda r: token_count(r['text_normalized_light']))

    short_ayah = next((r for r in unique_ayah_rows if 3 <= token_count(r['text_normalized_light']) <= 8 and int(r['ayah_no']) > 1), None)
    if short_ayah is None:
        short_ayah = next((r for r in unique_ayah_rows if token_count(r['text_normalized_light']) >= 3), unique_ayah_rows[0])

    long_ayah = next((r for r in ayah_rows if r['citation_string'] == 'Quran 2:282'), None)
    if long_ayah is None:
        long_ayah = max(unique_ayah_rows, key=lambda r: token_count(r['text_normalized_light']))

    static_window = next((r for r in passage_rows if int(r['window_size']) == 4), None)
    if static_window is None:
        static_window = max(passage_rows, key=lambda r: int(r['window_size']))

    exact_span_text, exact_span_citation, exact_span_meta = build_exact_span_text(
        grouped,
        span_len=5,
        min_tokens_required=18,
        max_tokens_allowed=80,
        avoid_citation=long_ayah['citation_string'],
    )

    from_text = exact_span_text
    giant_min_token_count = 60
    giant_exact_text, giant_exact_citation, giant_exact_meta = build_exact_span_text(
        grouped,
        span_len=8,
        min_tokens_required=giant_min_token_count,
        avoid_citation=exact_span_citation,
    )

    uthmani_lookup = {(int(r['surah_no']), int(r['ayah_no'])): r for r in uthmani_rows}
    short_ayah_key = (int(short_ayah['surah_no']), int(short_ayah['ayah_no']))
    uthmani_variant = uthmani_lookup.get(short_ayah_key)

    cases: list[TestCase] = [
        TestCase(
            case_id='01_full_exact_short_ayah',
            category='ayah_exact',
            query=normalize_space(short_ayah['text_display']),
            expectation='exact_single_ayah',
            expected_citation=short_ayah['citation_string'],
            expected_canonical_unit='single_ayah',
            note='Full exact short ayah should stay in ayah lane.',
        ),
        TestCase(
            case_id='02_clipped_exact_short_ayah',
            category='ayah_exact_excerpt',
            query=clip_text(short_ayah['text_display'], drop_left=1, drop_right=1, min_tokens=2),
            expectation='exact_single_ayah',
            expected_citation=short_ayah['citation_string'],
            expected_canonical_unit='single_ayah',
            note='Strict clipped excerpt of one short ayah should still resolve as ayah exact.',
        ),
        TestCase(
            case_id='03_full_exact_long_ayah',
            category='long_ayah_exact',
            query=normalize_space(long_ayah['text_display']),
            expectation='exact_single_ayah',
            expected_citation=long_ayah['citation_string'],
            expected_canonical_unit='single_ayah',
            note='Full exact long ayah should remain ayah, not passage.',
        ),
        TestCase(
            case_id='04_clipped_exact_long_ayah',
            category='long_ayah_exact_excerpt',
            query=clip_text(long_ayah['text_display'], drop_left=6, drop_right=6, min_tokens=12),
            expectation='exact_single_ayah',
            expected_citation=long_ayah['citation_string'],
            expected_canonical_unit='single_ayah',
            note='Strict clipped excerpt of a very long ayah should still resolve as ayah.',
        ),
        TestCase(
            case_id='05_full_exact_multi_ayah_span',
            category='span_exact',
            query=from_text,
            expectation='exact_contiguous_span',
            expected_citation=exact_span_citation,
            expected_canonical_unit='contiguous_span',
            note='Full exact 5-ayah block should resolve as a true contiguous passage span.',
            extra=exact_span_meta,
        ),
        TestCase(
            case_id='06_clipped_exact_multi_ayah_span',
            category='span_exact_excerpt',
            query=clip_text(from_text, drop_left=3, drop_right=3, min_tokens=12),
            expectation='exact_contiguous_span',
            expected_citation=exact_span_citation,
            expected_canonical_unit='contiguous_span',
            note='Strict clipped excerpt from a 5-ayah block should remain a true span exact.',
            extra=exact_span_meta,
        ),
        TestCase(
            case_id='07_full_exact_static_window',
            category='window_exact',
            query=normalize_space(static_window['text_display']),
            expectation='exact_static_window',
            expected_citation=static_window['citation_string'],
            expected_canonical_unit='static_window',
            note='Full exact static passage window should resolve as passage window exact.',
        ),
        TestCase(
            case_id='08_ayah_inside_wider_window',
            category='ayah_vs_window',
            query=normalize_space(short_ayah['text_display']),
            expectation='exact_single_ayah',
            expected_citation=short_ayah['citation_string'],
            expected_canonical_unit='single_ayah',
            note='If one ayah fully explains the query, a wider window should not steal credit.',
        ),
        TestCase(
            case_id='09_fuzzy_ayah_partial',
            category='ayah_fuzzy',
            query=mutate_middle_token(clip_text(short_ayah['text_display'], drop_left=0, drop_right=0, min_tokens=3)),
            expectation='not_exact',
            expected_citation=short_ayah['citation_string'],
            note='Noisy ayah query should not be promoted to exact.',
        ),
        TestCase(
            case_id='10_fuzzy_multi_ayah_partial',
            category='span_fuzzy',
            query=mutate_middle_token(clip_text(from_text, drop_left=2, drop_right=2, min_tokens=10)),
            expectation='not_exact',
            expected_citation=exact_span_citation,
            note='Noisy multi-ayah query should not be promoted to exact.',
        ),
        TestCase(
            case_id='11_giant_exact_multi_ayah',
            category='giant_exact',
            query=normalize_space(giant_exact_text),
            expectation='giant_exact_passage',
            expected_citation=giant_exact_citation,
            expected_canonical_unit='contiguous_span',
            note='Giant exact multi-ayah block should resolve as passage exact via giant/span engine.',
            extra=giant_exact_meta,
        ),
        TestCase(
            case_id='12_giant_clipped_exact_multi_ayah',
            category='giant_exact_excerpt',
            query=clip_text(giant_exact_text, drop_left=6, drop_right=6, min_tokens=18),
            expectation='giant_exact_passage',
            expected_citation=giant_exact_citation,
            expected_canonical_unit='contiguous_span',
            note='Giant strict excerpt should remain exact passage, not degrade to fuzzy.',
            extra=giant_exact_meta,
        ),
        TestCase(
            case_id='13_uthmani_exact_variant',
            category='runtime_axis',
            query=normalize_space(uthmani_variant['text_display']) if uthmani_variant else normalize_space(short_ayah['text_display']),
            expectation='exact_single_ayah',
            expected_citation=short_ayah['citation_string'],
            expected_canonical_unit='single_ayah',
            note='Uthmani/simple variant should still resolve to the same ayah citation.',
        ),
        TestCase(
            case_id='14_no_reliable_match',
            category='negative',
            query='هذا نص عربي عادي لا يمثل آية قرآنية ويجب ألا يعتبر مطابقا',
            expectation='negative_no_exact',
            note='Non-Quranic Arabic should not be reported as exact.',
        ),
    ]

    return cases


def validate_case(case: TestCase, response: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    best = response.get('best_match') or {}
    preferred_lane = response.get('preferred_lane')
    match_status = response.get('match_status')
    citation = best.get('citation')
    canonical_unit_type = best.get('canonical_unit_type')
    retrieval_engine = best.get('retrieval_engine')

    if case.expectation == 'exact_single_ayah':
        if preferred_lane != 'ayah':
            failures.append(f'expected preferred_lane=ayah, got {preferred_lane}')
        if match_status != 'Exact match found':
            failures.append(f'expected Exact match found, got {match_status}')
        if case.expected_citation and citation != case.expected_citation:
            failures.append(f'expected citation={case.expected_citation}, got {citation}')
        if case.expected_canonical_unit and canonical_unit_type != case.expected_canonical_unit:
            failures.append(
                f'expected canonical_unit_type={case.expected_canonical_unit}, got {canonical_unit_type}'
            )

    elif case.expectation == 'exact_contiguous_span':
        if preferred_lane != 'passage':
            failures.append(f'expected preferred_lane=passage, got {preferred_lane}')
        if match_status != 'Exact match found':
            failures.append(f'expected Exact match found, got {match_status}')
        if citation != case.expected_citation:
            failures.append(f'expected citation={case.expected_citation}, got {citation}')
        if canonical_unit_type != 'contiguous_span':
            failures.append(f'expected canonical_unit_type=contiguous_span, got {canonical_unit_type}')

    elif case.expectation == 'exact_static_window':
        if preferred_lane != 'passage':
            failures.append(f'expected preferred_lane=passage, got {preferred_lane}')
        if match_status != 'Exact match found':
            failures.append(f'expected Exact match found, got {match_status}')
        if citation != case.expected_citation:
            failures.append(f'expected citation={case.expected_citation}, got {citation}')
        if canonical_unit_type != 'static_window':
            failures.append(f'expected canonical_unit_type=static_window, got {canonical_unit_type}')

    elif case.expectation == 'not_exact':
        if match_status == 'Exact match found':
            failures.append('expected a non-exact result, but got Exact match found')

    elif case.expectation == 'giant_exact_passage':
        if preferred_lane != 'passage':
            failures.append(f'expected preferred_lane=passage, got {preferred_lane}')
        if match_status != 'Exact match found':
            failures.append(f'expected Exact match found, got {match_status}')
        if citation != case.expected_citation:
            failures.append(f'expected citation={case.expected_citation}, got {citation}')
        if canonical_unit_type != 'contiguous_span':
            failures.append(f'expected canonical_unit_type=contiguous_span, got {canonical_unit_type}')
        if retrieval_engine not in {'giant_exact_anchor', 'surah_span_exact', 'static_exact_window'}:
            failures.append(f'expected giant/span exact retrieval_engine, got {retrieval_engine}')

    elif case.expectation == 'negative_no_exact':
        if match_status == 'Exact match found':
            failures.append('expected non-exact negative result, but got Exact match found')

    else:
        failures.append(f'unknown expectation type: {case.expectation}')

    return (len(failures) == 0), failures


def write_csv_report(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        'case_id', 'category', 'passed', 'preferred_lane', 'match_status', 'citation',
        'canonical_unit_type', 'retrieval_engine', 'decision_rule', 'confidence', 'failures', 'query_preview'
    ]
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description='Run a full Quran verifier regression sweep against the in-process API app.')
    parser.add_argument('--repo-root', type=Path, default=Path('.'), help='Path to the Dalil Verify repo root.')
    parser.add_argument('--output-dir', type=Path, default=None, help='Directory for JSON/CSV reports.')
    parser.add_argument('--case-filter', type=str, default='', help='Optional substring filter on case_id/category.')
    parser.add_argument('--strict-exit', action='store_true', help='Exit with code 1 if any case fails.')
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    if not (repo_root / 'apps' / 'api' / 'main.py').exists():
        print(f'[ERROR] Repo root does not look correct: {repo_root}', file=sys.stderr)
        return 2

    os.chdir(repo_root)
    sys.path.insert(0, str(repo_root))

    from apps.api import main as api_main

    api_main.QURAN_DATA_PATH = repo_root / 'data' / 'processed' / 'quran' / 'quran_arabic_canonical.csv'
    api_main.QURAN_PASSAGE_DATA_PATH = repo_root / 'data' / 'processed' / 'quran_passages' / 'quran_passage_windows_v1.csv'
    api_main.QURAN_UTHMANI_DATA_PATH = repo_root / 'data' / 'processed' / 'quran_uthmani' / 'quran_arabic_uthmani_canonical.csv'
    api_main.QURAN_UTHMANI_PASSAGE_DATA_PATH = repo_root / 'data' / 'processed' / 'quran_uthmani_passages' / 'quran_uthmani_passage_windows_v1.csv'
    api_main.QURAN_EN_TRANSLATION_PATH = repo_root / 'data' / 'processed' / 'quran_translations' / 'quran_en_single_translation.csv'

    cases = build_cases(repo_root)
    if args.case_filter:
        needle = args.case_filter.lower()
        cases = [c for c in cases if needle in c.case_id.lower() or needle in c.category.lower()]
        if not cases:
            print(f'[ERROR] No cases matched filter: {args.case_filter}', file=sys.stderr)
            return 2

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = (args.output_dir or (repo_root / 'reports' / f'quran_regression_{ts}')).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_cases_path = output_dir / 'generated_cases.json'
    json_report_path = output_dir / 'full_regression_report.json'
    csv_report_path = output_dir / 'full_regression_summary.csv'

    generated_cases_payload = [
        {
            'case_id': c.case_id,
            'category': c.category,
            'expectation': c.expectation,
            'note': c.note,
            'expected_citation': c.expected_citation,
            'expected_canonical_unit': c.expected_canonical_unit,
            'query': c.query,
            'extra': c.extra or {},
        }
        for c in cases
    ]
    generated_cases_path.write_text(json.dumps(generated_cases_payload, ensure_ascii=False, indent=2), encoding='utf-8')

    detail_rows: list[dict[str, Any]] = []
    csv_rows: list[dict[str, Any]] = []

    # Initialize runtimes directly without spinning up the web server.
    api_main.SIMPLE_RUNTIME = api_main._load_runtime(
        "simple", api_main.QURAN_DATA_PATH, api_main.QURAN_PASSAGE_DATA_PATH, required=True
    )
    api_main.UTHMANI_RUNTIME = api_main._load_runtime(
        "uthmani", api_main.QURAN_UTHMANI_DATA_PATH, api_main.QURAN_UTHMANI_PASSAGE_DATA_PATH, required=False
    )
    api_main.ENGLISH_TRANSLATION_MAP, api_main.ENGLISH_TRANSLATION_INFO = api_main.load_english_translation_map(
        api_main.QURAN_EN_TRANSLATION_PATH
    )

    if api_main.SIMPLE_RUNTIME is None:
        print('[ERROR] Simple runtime did not load.', file=sys.stderr)
        return 2

    for case in cases:
        raw_query = case.query.strip()
        query_route = api_main.detect_quran_query_route(raw_query)
        matching_query, preprocessing_meta = api_main.sanitize_quran_text_for_matching_with_meta(raw_query)
        if not matching_query:
            payload = {'query': raw_query, 'preferred_lane': 'none', 'match_status': 'Cannot assess', 'confidence': 'low', 'best_match': None, 'debug': {}}
        else:
            evaluations: list[dict[str, Any]] = []
            fallback_trigger_reason = 'single_runtime_only'
            for runtime in api_main._runtime_order(query_route):
                evaluation = api_main._evaluate_runtime(
                    runtime,
                    raw_query=raw_query,
                    matching_query=matching_query,
                    debug=True,
                    query_preprocessing=preprocessing_meta,
                    query_routing=query_route,
                )
                evaluations.append(evaluation)
                fallback_trigger_reason = api_main._fallback_trigger_reason(query_route, evaluation)
                if api_main._should_stop_after_runtime(query_route, evaluation):
                    break

            selected_evaluation, evaluations = api_main._choose_runtime_evaluation(query_route, evaluations)
            fusion_output = selected_evaluation['fusion_output']
            payload = api_main.compact_result_for_api(
                fusion_output,
                debug=True,
                english_translation_map=api_main.ENGLISH_TRANSLATION_MAP,
                query_preprocessing=fusion_output.get('query_preprocessing'),
                query_routing={**query_route, 'fallback_trigger_reason': fallback_trigger_reason},
                selected_runtime=selected_evaluation['runtime'],
                runtime_evaluations=[
                    {
                        'runtime': ev['runtime'],
                        'preferred_lane': ev['public_response'].get('preferred_lane'),
                        'match_status': ev['public_response'].get('match_status'),
                        'confidence': ev['public_response'].get('confidence'),
                        'best_citation': ((ev['public_response'].get('best_match') or {}).get('citation')),
                        'stage_timings': ev.get('stage_timings') or {},
                    }
                    for ev in evaluations
                ],
                stage_timings={'request_total_ms': 0.0},
            )

        passed, failures = validate_case(case, payload)
        best = payload.get('best_match') or {}
        debug = payload.get('debug') or {}

        detail_rows.append({
            'case_id': case.case_id,
            'category': case.category,
            'note': case.note,
            'expectation': case.expectation,
            'expected_citation': case.expected_citation,
            'expected_canonical_unit': case.expected_canonical_unit,
            'query': case.query,
            'query_token_count': len(case.query.split()),
            'passed': passed,
            'failures': failures,
            'response': payload,
        })

        csv_rows.append({
            'case_id': case.case_id,
            'category': case.category,
            'passed': 'PASS' if passed else 'FAIL',
            'preferred_lane': payload.get('preferred_lane'),
            'match_status': payload.get('match_status'),
            'citation': best.get('citation'),
            'canonical_unit_type': best.get('canonical_unit_type'),
            'retrieval_engine': best.get('retrieval_engine'),
            'decision_rule': debug.get('decision_rule'),
            'confidence': payload.get('confidence'),
            'failures': ' | '.join(failures),
            'query_preview': case.query[:120],
        })

    total = len(detail_rows)
    passed_count = sum(1 for row in detail_rows if row['passed'])
    failed_count = total - passed_count

    report = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'repo_root': str(repo_root),
        'total_cases': total,
        'passed_cases': passed_count,
        'failed_cases': failed_count,
        'pass_rate': round((passed_count / total) * 100.0, 2) if total else 0.0,
        'cases': detail_rows,
    }
    json_report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    write_csv_report(csv_report_path, csv_rows)

    print('\n=== FULL QURAN REGRESSION SUITE ===')
    print(f'Repo root   : {repo_root}')
    print(f'Reports dir : {output_dir}')
    print(f'Total cases : {total}')
    print(f'Passed      : {passed_count}')
    print(f'Failed      : {failed_count}')
    print(f'Pass rate   : {report["pass_rate"]}%')
    print('')
    for row in csv_rows:
        status_icon = '✅' if row['passed'] == 'PASS' else '❌'
        print(f"{status_icon} {row['case_id']}: lane={row['preferred_lane']} | status={row['match_status']} | citation={row['citation']} | unit={row['canonical_unit_type']} | engine={row['retrieval_engine']}")
        if row['failures']:
            print(f"   ↳ {row['failures']}")

    print('')
    print(f'Generated cases : {generated_cases_path}')
    print(f'JSON report     : {json_report_path}')
    print(f'CSV summary     : {csv_report_path}')

    if args.strict_exit and failed_count > 0:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
