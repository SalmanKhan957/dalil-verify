from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipelines.evaluation.suites.mvp_acceptance import (
    HttpClient,
    LocalAppClient,
    build_markdown_report,
    load_suite,
    run_suite,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DALIL MVP acceptance harness.")
    parser.add_argument(
        "--suite",
        default="evaluation/goldens/mvp_acceptance_cases.json",
        help="Path to the MVP acceptance suite JSON file.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Optional running DALIL base URL. If omitted, the local FastAPI app is used via TestClient.",
    )
    parser.add_argument(
        "--report-dir",
        default="evaluation/reports/mvp_acceptance",
        help="Directory where JSON and Markdown reports will be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    suite = load_suite(args.suite)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    client = HttpClient(args.base_url) if args.base_url else LocalAppClient()
    results, summary = run_suite(suite, client)

    json_report = report_dir / "mvp_acceptance_report.json"
    md_report = report_dir / "mvp_acceptance_report.md"

    json_report.write_text(
        json.dumps(
            {
                "summary": summary,
                "results": [
                    {
                        "case_id": item.case_id,
                        "category": item.category,
                        "query": item.query,
                        "passed": item.passed,
                        "checks": item.checks,
                        "failure_reasons": item.failure_reasons,
                    }
                    for item in results
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    md_report.write_text(build_markdown_report(summary), encoding="utf-8")

    print(f"Wrote JSON report -> {json_report}")
    print(f"Wrote Markdown report -> {md_report}")
    print(f"All gates passed: {'yes' if summary['all_gates_passed'] else 'no'}")
    return 0 if summary["all_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
