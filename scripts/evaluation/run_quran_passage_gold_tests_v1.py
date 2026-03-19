from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.evaluation.compare_quran_ayah_vs_passage import build_fusion_output
from scripts.evaluation.quran_verifier_baseline import (
    build_result as build_ayah_result,
    compute_best_matches as compute_ayah_matches,
    load_quran_dataset,
)
from scripts.evaluation.quran_passage_verifier_baseline import (
    build_passage_result,
    compute_best_passage_matches,
    load_quran_passage_dataset,
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
        raise ValueError("No passage gold tests found.")

    return tests


def parse_acceptable_citations(value: str) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(";") if v.strip()]


def is_yes(value: str) -> bool:
    return (value or "").strip().lower() in {"yes", "true", "1"}


def evaluate_one(
    test: dict[str, str],
    quran_rows: list[dict[str, Any]],
    passage_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    query = test["query"]

    ayah_candidates = compute_ayah_matches(query, quran_rows, top_k=5)
    passage_candidates = compute_best_passage_matches(query, passage_rows, top_k=5)

    ayah_result = build_ayah_result(query, ayah_candidates)
    passage_result = build_passage_result(query, passage_candidates)

    fusion_output = build_fusion_output(
        query=query,
        ayah_result=ayah_result,
        passage_result=passage_result,
    )

    preferred_lane = fusion_output["preferred_lane"]
    preferred_result = fusion_output["preferred_result"] or {}
    preferred_best = preferred_result.get("best_match") or {}

    actual_lane = preferred_lane
    actual_status = preferred_result.get("match_status", "")
    actual_citation = preferred_best.get("citation", "")

    expected_lane = test["expected_preferred_lane"]
    expected_status = test["expected_match_status"]
    expected_primary_citation = (test.get("expected_primary_citation") or "").strip()
    acceptable_citations = parse_acceptable_citations(test.get("acceptable_citations", ""))
    requires_longer_passage_support = is_yes(test.get("requires_longer_passage_support", ""))

    lane_pass = actual_lane == expected_lane
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

    in_core_scope = not requires_longer_passage_support

    overall_pass_core = (
        lane_pass and classification_pass and flexible_retrieval_pass
        if in_core_scope
        else None
    )

    return {
        "test_id": test["test_id"],
        "category": test["category"],
        "query": query,
        "expected_preferred_lane": expected_lane,
        "actual_preferred_lane": actual_lane,
        "lane_pass": lane_pass,
        "expected_match_status": expected_status,
        "actual_match_status": actual_status,
        "classification_pass": classification_pass,
        "expected_primary_citation": expected_primary_citation,
        "acceptable_citations": ";".join(acceptable_citations),
        "actual_primary_citation": actual_citation,
        "strict_retrieval_pass": strict_retrieval_pass,
        "flexible_retrieval_pass": flexible_retrieval_pass,
        "requires_longer_passage_support": requires_longer_passage_support,
        "in_core_scope": in_core_scope,
        "overall_pass_core": overall_pass_core,
        "rationale": fusion_output.get("rationale", ""),
        "notes": test.get("notes", ""),
    }


def write_detailed_report(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "test_id",
        "category",
        "query",
        "expected_preferred_lane",
        "actual_preferred_lane",
        "lane_pass",
        "expected_match_status",
        "actual_match_status",
        "classification_pass",
        "expected_primary_citation",
        "acceptable_citations",
        "actual_primary_citation",
        "strict_retrieval_pass",
        "flexible_retrieval_pass",
        "requires_longer_passage_support",
        "in_core_scope",
        "overall_pass_core",
        "rationale",
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

    lane_passed = sum(1 for r in rows if r["lane_pass"])
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
        "lane_pass_rate_all": pct(lane_passed, total_tests),
        "strict_retrieval_pass_rate_all": pct(strict_retrieval_passed, total_tests),
        "flexible_retrieval_pass_rate_all": pct(flexible_retrieval_passed, total_tests),
        "classification_pass_rate_all": pct(classification_passed, total_tests),
        "core_overall_pass_rate": pct(core_passed, len(core_rows)),
        "core_passed": core_passed,
        "core_failed": core_failed,
        "future_scope_cases": [r for r in rows if not r["in_core_scope"]],
        "core_failures": [r for r in core_rows if r["overall_pass_core"] is False],
        "by_category": by_category,
    }


def write_summary(summary: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Quran passage gold tests v1.")
    parser.add_argument(
        "--ayah-data",
        type=str,
        default="data/processed/quran/quran_arabic_canonical.csv",
    )
    parser.add_argument(
        "--passage-data",
        type=str,
        default="data/processed/quran_passages/quran_passage_windows_v1.csv",
    )
    parser.add_argument(
        "--tests",
        type=str,
        default="data/gold_tests/quran_passage_gold_tests_v1.csv",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="data/processed/evaluation",
    )
    args = parser.parse_args()

    quran_rows = load_quran_dataset(Path(args.ayah_data))
    passage_rows = load_quran_passage_dataset(Path(args.passage_data))
    tests = load_gold_tests(Path(args.tests))

    detailed_results = [evaluate_one(test, quran_rows, passage_rows) for test in tests]
    summary = build_summary(detailed_results)

    detailed_csv_path = Path(args.out_dir) / "quran_passage_gold_test_results_v1.csv"
    summary_json_path = Path(args.out_dir) / "quran_passage_gold_test_summary_v1.json"

    write_detailed_report(detailed_results, detailed_csv_path)
    write_summary(summary, summary_json_path)

    print("Evaluation complete.")
    print(f"Detailed report: {detailed_csv_path}")
    print(f"Summary report:  {summary_json_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()