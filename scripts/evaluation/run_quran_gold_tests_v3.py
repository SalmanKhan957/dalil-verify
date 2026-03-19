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


def parse_acceptable_citations(value: str) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(";") if v.strip()]


def is_yes(value: str) -> bool:
    return (value or "").strip().lower() in {"yes", "true", "1"}


def evaluate_one(test: dict[str, str], quran_rows: list[dict[str, Any]]) -> dict[str, Any]:
    query = test["query"]
    candidates = compute_best_matches(query, quran_rows, top_k=5)
    result = build_result(query, candidates)

    actual_mode = result["mode"]
    actual_status = result["match_status"]
    actual_citation = result["best_match"]["citation"] if result.get("best_match") else ""

    expected_mode = test["expected_mode"]
    expected_status = test["expected_match_status"]
    expected_primary_citation = (test.get("expected_primary_citation") or "").strip()
    acceptable_citations = parse_acceptable_citations(test.get("acceptable_citations", ""))
    requires_passage_support = is_yes(test.get("requires_passage_support", ""))

    mode_pass = actual_mode == expected_mode
    classification_pass = actual_status == expected_status

    if expected_primary_citation:
        strict_retrieval_pass = actual_citation == expected_primary_citation
    else:
        strict_retrieval_pass = True

    if acceptable_citations:
        flexible_retrieval_pass = actual_citation in acceptable_citations
    elif expected_primary_citation:
        flexible_retrieval_pass = actual_citation == expected_primary_citation
    else:
        flexible_retrieval_pass = True

    # Core KPI excludes future-scope passage-support cases
    in_core_scope = not requires_passage_support

    overall_pass_core = (
        mode_pass and classification_pass and flexible_retrieval_pass
        if in_core_scope
        else None
    )

    passage_blocked = (
        requires_passage_support and not strict_retrieval_pass
    )

    return {
        "test_id": test["test_id"],
        "category": test["category"],
        "query": query,
        "expected_mode": expected_mode,
        "actual_mode": actual_mode,
        "mode_pass": mode_pass,
        "expected_match_status": expected_status,
        "actual_match_status": actual_status,
        "classification_pass": classification_pass,
        "expected_primary_citation": expected_primary_citation,
        "acceptable_citations": ";".join(acceptable_citations),
        "actual_primary_citation": actual_citation,
        "strict_retrieval_pass": strict_retrieval_pass,
        "flexible_retrieval_pass": flexible_retrieval_pass,
        "requires_passage_support": requires_passage_support,
        "in_core_scope": in_core_scope,
        "passage_blocked": passage_blocked,
        "overall_pass_core": overall_pass_core,
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
        "classification_pass",
        "expected_primary_citation",
        "acceptable_citations",
        "actual_primary_citation",
        "strict_retrieval_pass",
        "flexible_retrieval_pass",
        "requires_passage_support",
        "in_core_scope",
        "passage_blocked",
        "overall_pass_core",
        "notes",
    ]

    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def pct(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_tests = len(rows)
    core_rows = [r for r in rows if r["in_core_scope"]]
    future_rows = [r for r in rows if not r["in_core_scope"]]

    mode_passed = sum(1 for r in rows if r["mode_pass"])
    strict_retrieval_passed = sum(1 for r in rows if r["strict_retrieval_pass"])
    flexible_retrieval_passed = sum(1 for r in rows if r["flexible_retrieval_pass"])
    classification_passed = sum(1 for r in rows if r["classification_pass"])

    core_passed = sum(1 for r in core_rows if r["overall_pass_core"] is True)
    core_failed = sum(1 for r in core_rows if r["overall_pass_core"] is False)

    by_category: dict[str, dict[str, int]] = {}
    for r in rows:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "core_passed": 0, "core_failed": 0}
        by_category[cat]["total"] += 1
        if r["overall_pass_core"] is True:
            by_category[cat]["core_passed"] += 1
        elif r["overall_pass_core"] is False:
            by_category[cat]["core_failed"] += 1

    return {
        "total_tests": total_tests,
        "core_scope_tests": len(core_rows),
        "future_scope_tests": len(future_rows),
        "mode_pass_rate_all": pct(mode_passed, total_tests),
        "strict_retrieval_pass_rate_all": pct(strict_retrieval_passed, total_tests),
        "flexible_retrieval_pass_rate_all": pct(flexible_retrieval_passed, total_tests),
        "classification_pass_rate_all": pct(classification_passed, total_tests),
        "core_overall_pass_rate": pct(core_passed, len(core_rows)),
        "core_passed": core_passed,
        "core_failed": core_failed,
        "passage_support_cases": [r for r in rows if r["requires_passage_support"]],
        "core_failures": [r for r in core_rows if r["overall_pass_core"] is False],
        "by_category": by_category,
    }


def write_summary(summary: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Quran gold tests v3.")
    parser.add_argument(
        "--data",
        type=str,
        default="data/processed/quran/quran_arabic_canonical.csv",
        help="Path to canonical Quran CSV.",
    )
    parser.add_argument(
        "--tests",
        type=str,
        default="data/gold_tests/quran_gold_tests_v3.csv",
        help="Path to Quran gold tests v3 CSV.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="data/processed/evaluation",
        help="Directory for evaluation outputs.",
    )
    args = parser.parse_args()

    quran_rows = load_quran_dataset(Path(args.data))
    tests = load_gold_tests(Path(args.tests))

    detailed_results = [evaluate_one(test, quran_rows) for test in tests]
    summary = build_summary(detailed_results)

    detailed_csv_path = Path(args.out_dir) / "quran_gold_test_results_v3.csv"
    summary_json_path = Path(args.out_dir) / "quran_gold_test_summary_v3.json"

    write_detailed_report(detailed_results, detailed_csv_path)
    write_summary(summary, summary_json_path)

    print("Evaluation complete.")
    print(f"Detailed report: {detailed_csv_path}")
    print(f"Summary report:  {summary_json_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()