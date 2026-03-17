from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.evaluation.quran_verifier_baseline import (
    load_quran_dataset,
    compute_best_matches,
    build_result,
)


def load_gold_tests(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Gold test CSV not found: {csv_path}")

    tests: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tests.append(row)

    if not tests:
        raise ValueError("No gold tests found.")

    return tests


def evaluate_one(test: dict[str, str], quran_rows: list[dict[str, Any]]) -> dict[str, Any]:
    query = test["query"]
    candidates = compute_best_matches(query, quran_rows, top_k=5)
    result = build_result(query, candidates)

    actual_mode = result["mode"]
    actual_status = result["match_status"]
    actual_citation = (
        result["best_match"]["citation"] if result.get("best_match") else ""
    )

    expected_mode = test["expected_mode"]
    expected_status = test["expected_match_status"]
    expected_citation = test["expected_primary_citation"]

    mode_pass = actual_mode == expected_mode
    status_pass = actual_status == expected_status

    if expected_citation.strip():
        citation_pass = actual_citation == expected_citation
    else:
        citation_pass = True

    overall_pass = mode_pass and status_pass and citation_pass

    return {
        "test_id": test["test_id"],
        "category": test["category"],
        "query": query,
        "expected_mode": expected_mode,
        "actual_mode": actual_mode,
        "mode_pass": mode_pass,
        "expected_match_status": expected_status,
        "actual_match_status": actual_status,
        "status_pass": status_pass,
        "expected_primary_citation": expected_citation,
        "actual_primary_citation": actual_citation,
        "citation_pass": citation_pass,
        "overall_pass": overall_pass,
        "notes": test.get("notes", ""),
    }


def write_detailed_report(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "test_id",
        "category",
        "query",
        "expected_mode",
        "actual_mode",
        "mode_pass",
        "expected_match_status",
        "actual_match_status",
        "status_pass",
        "expected_primary_citation",
        "actual_primary_citation",
        "citation_pass",
        "overall_pass",
        "notes",
    ]

    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    passed = sum(1 for r in rows if r["overall_pass"])
    failed = total - passed

    mode_passed = sum(1 for r in rows if r["mode_pass"])
    status_passed = sum(1 for r in rows if r["status_pass"])
    citation_passed = sum(1 for r in rows if r["citation_pass"])

    by_category: dict[str, dict[str, int]] = {}
    for r in rows:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "passed": 0, "failed": 0}
        by_category[cat]["total"] += 1
        if r["overall_pass"]:
            by_category[cat]["passed"] += 1
        else:
            by_category[cat]["failed"] += 1

    failures = [r for r in rows if not r["overall_pass"]]

    return {
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round((passed / total) * 100, 2) if total else 0.0,
        "mode_pass_rate": round((mode_passed / total) * 100, 2) if total else 0.0,
        "status_pass_rate": round((status_passed / total) * 100, 2) if total else 0.0,
        "citation_pass_rate": round((citation_passed / total) * 100, 2) if total else 0.0,
        "by_category": by_category,
        "failures": failures,
    }


def write_summary(summary: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Quran gold tests against the baseline verifier."
    )
    parser.add_argument(
        "--data",
        type=str,
        default="data/processed/quran/quran_arabic_canonical.csv",
        help="Path to canonical Quran CSV.",
    )
    parser.add_argument(
        "--tests",
        type=str,
        default="data/gold_tests/quran_gold_tests_v1.csv",
        help="Path to Quran gold tests CSV.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="data/processed/evaluation",
        help="Directory for output reports.",
    )
    args = parser.parse_args()

    data_path = Path(args.data)
    tests_path = Path(args.tests)
    out_dir = Path(args.out_dir)

    quran_rows = load_quran_dataset(data_path)
    tests = load_gold_tests(tests_path)

    detailed_results = [evaluate_one(test, quran_rows) for test in tests]
    summary = build_summary(detailed_results)

    detailed_csv_path = out_dir / "quran_gold_test_results_v1.csv"
    summary_json_path = out_dir / "quran_gold_test_summary_v1.json"

    write_detailed_report(detailed_results, detailed_csv_path)
    write_summary(summary, summary_json_path)

    print("Evaluation complete.")
    print(f"Detailed report: {detailed_csv_path}")
    print(f"Summary report:  {summary_json_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()