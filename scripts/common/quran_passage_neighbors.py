from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def build_passage_row_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        canonical_source_id = str(row.get("canonical_source_id") or "")
        if canonical_source_id and canonical_source_id not in lookup:
            lookup[canonical_source_id] = row
    return lookup


def load_passage_neighbor_lookup(
    jsonl_path: Path,
) -> dict[str, dict[tuple[int, str], list[dict[str, Any]]]]:
    """Load precomputed passage-neighbor rows keyed by runtime/corpus.

    Returns:
        {
            "simple": {(2, "quran_passage:15:30-31:ar"): [neighbor, ...]},
            "uthmani": {...},
        }
    """
    grouped: dict[str, dict[tuple[int, str], list[dict[str, Any]]]] = defaultdict(dict)
    if not jsonl_path.exists():
        return {"simple": {}, "uthmani": {}}

    with jsonl_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            matching_corpus = str(payload.get("matching_corpus") or "")
            source_canonical_id = str(payload.get("source_canonical_id") or "")
            window_size = payload.get("window_size")
            if not matching_corpus or not source_canonical_id or window_size is None:
                continue
            grouped[matching_corpus][(int(window_size), source_canonical_id)] = list(payload.get("neighbors") or [])

    return {
        "simple": grouped.get("simple", {}),
        "uthmani": grouped.get("uthmani", {}),
    }
