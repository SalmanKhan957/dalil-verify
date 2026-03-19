from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")

    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Quran lane analytics logs.")
    parser.add_argument(
        "--log",
        type=str,
        default="logs/verify_quran.jsonl",
        help="Path to verify_quran JSONL log file.",
    )
    args = parser.parse_args()

    rows = load_jsonl(Path(args.log))

    total = len(rows)
    preferred_lane_counter = Counter(r.get("preferred_lane") for r in rows)
    decision_rule_counter = Counter(r.get("decision_rule") for r in rows)

    token_buckets = defaultdict(int)
    for r in rows:
        tc = r.get("query_token_count") or 0
        if tc <= 3:
            token_buckets["1-3"] += 1
        elif tc <= 6:
            token_buckets["4-6"] += 1
        elif tc <= 10:
            token_buckets["7-10"] += 1
        else:
            token_buckets["11+"] += 1

    summary = {
        "total_requests": total,
        "preferred_lane_counts": dict(preferred_lane_counter),
        "decision_rule_counts": dict(decision_rule_counter),
        "query_token_buckets": dict(token_buckets),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()