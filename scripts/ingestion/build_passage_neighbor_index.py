from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.evaluation.quran_passage_verifier_baseline import load_quran_passage_dataset

QURAN_PASSAGE_DATA_PATH = Path("data/processed/quran_passages/quran_passage_windows_v1.csv")
QURAN_UTHMANI_PASSAGE_DATA_PATH = Path("data/processed/quran_uthmani_passages/quran_uthmani_passage_windows_v1.csv")
DEFAULT_OUTPUT_PATH = Path("data/processed/quran_passage_neighbors/passage_neighbors_v1.jsonl")


def _unique_tokens(row: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for token in row.get("tokens_light") or []:
        if token and token not in seen:
            seen.add(token)
            ordered.append(token)
    return ordered


def _build_token_document_frequency(rows: list[dict[str, Any]]) -> Counter[str]:
    df: Counter[str] = Counter()
    for row in rows:
        df.update(set(_unique_tokens(row)))
    return df


def _build_inverted_index(rows: list[dict[str, Any]]) -> dict[str, list[int]]:
    postings: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        for token in set(_unique_tokens(row)):
            postings[token].append(idx)
    return dict(postings)


def _candidate_pool(
    row: dict[str, Any],
    *,
    postings: dict[str, list[int]],
    document_frequency: Counter[str],
    max_anchor_tokens: int = 6,
) -> set[int]:
    tokens = _unique_tokens(row)
    if not tokens:
        return set()

    anchors = sorted(tokens, key=lambda t: (document_frequency.get(t, 10**9), t))[:max_anchor_tokens]
    candidate_ids: set[int] = set()
    for token in anchors:
        candidate_ids.update(postings.get(token, []))
    return candidate_ids


def _neighbor_score(source: dict[str, Any], candidate: dict[str, Any]) -> tuple[float, int, float, int]:
    source_tokens = set(_unique_tokens(source))
    candidate_tokens = set(_unique_tokens(candidate))
    if not source_tokens or not candidate_tokens:
        return (0.0, 0, 0.0, 10**9)

    overlap = len(source_tokens.intersection(candidate_tokens))
    union = len(source_tokens.union(candidate_tokens))
    jaccard = (overlap / union) if union else 0.0
    coverage_vs_source = (overlap / len(source_tokens)) * 100.0
    missing_source_tokens = max(len(source_tokens) - overlap, 0)
    score = overlap * 10.0 + jaccard * 100.0 + coverage_vs_source
    return (score, overlap, coverage_vs_source, missing_source_tokens)


def _build_runtime_neighbors(
    *,
    matching_corpus: str,
    rows: list[dict[str, Any]],
    max_window_size: int,
    top_k: int,
    min_shared_tokens: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    rows_by_window: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        window_size = int(row.get("window_size") or 0)
        if window_size <= 0 or window_size > max_window_size:
            continue
        rows_by_window[window_size].append(row)

    for window_size, window_rows in rows_by_window.items():
        postings = _build_inverted_index(window_rows)
        df = _build_token_document_frequency(window_rows)
        canonical_ids = [str(r.get("canonical_source_id") or "") for r in window_rows]
        row_by_index = {idx: row for idx, row in enumerate(window_rows)}

        for source_idx, source_row in enumerate(window_rows):
            source_canonical_id = canonical_ids[source_idx]
            if not source_canonical_id:
                continue

            pool = _candidate_pool(source_row, postings=postings, document_frequency=df)
            ranked: list[tuple[tuple[float, int, float, int], dict[str, Any]]] = []
            source_surah = int(source_row.get("surah_no") or 0)

            for candidate_idx in pool:
                if candidate_idx == source_idx:
                    continue
                candidate_row = row_by_index[candidate_idx]
                candidate_canonical_id = str(candidate_row.get("canonical_source_id") or "")
                if not candidate_canonical_id or candidate_canonical_id == source_canonical_id:
                    continue
                if int(candidate_row.get("surah_no") or 0) == source_surah:
                    continue

                score, overlap, coverage_vs_source, missing_source_tokens = _neighbor_score(source_row, candidate_row)
                if overlap < min_shared_tokens:
                    continue

                ranked.append(((score, overlap, coverage_vs_source, -missing_source_tokens), candidate_row))

            ranked.sort(key=lambda item: item[0], reverse=True)
            neighbors: list[dict[str, Any]] = []
            for rank, (_, candidate_row) in enumerate(ranked[:top_k], start=1):
                candidate_tokens = set(_unique_tokens(candidate_row))
                source_tokens = set(_unique_tokens(source_row))
                overlap = len(source_tokens.intersection(candidate_tokens))
                coverage_vs_source = (overlap / len(source_tokens)) * 100.0 if source_tokens else 0.0
                neighbors.append({
                    "canonical_source_id": str(candidate_row.get("canonical_source_id") or ""),
                    "surah_no": int(candidate_row.get("surah_no") or 0),
                    "start_ayah": int(candidate_row.get("start_ayah") or 0),
                    "end_ayah": int(candidate_row.get("end_ayah") or 0),
                    "window_size": int(candidate_row.get("window_size") or window_size),
                    "precomputed_rank": rank,
                    "token_overlap_count": overlap,
                    "token_coverage_vs_source": round(coverage_vs_source, 2),
                    "missing_source_tokens": max(len(source_tokens) - overlap, 0),
                })

            if neighbors:
                records.append({
                    "matching_corpus": matching_corpus,
                    "source_canonical_id": source_canonical_id,
                    "window_size": window_size,
                    "neighbors": neighbors,
                })

    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Build precomputed Quran passage-neighbor index.")
    parser.add_argument("--simple-path", type=Path, default=QURAN_PASSAGE_DATA_PATH)
    parser.add_argument("--uthmani-path", type=Path, default=QURAN_UTHMANI_PASSAGE_DATA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-window-size", type=int, default=4)
    parser.add_argument("--min-shared-tokens", type=int, default=4)
    args = parser.parse_args()

    all_records: list[dict[str, Any]] = []

    if args.simple_path.exists():
        simple_rows = load_quran_passage_dataset(args.simple_path)
        all_records.extend(
            _build_runtime_neighbors(
                matching_corpus="simple",
                rows=simple_rows,
                max_window_size=args.max_window_size,
                top_k=args.top_k,
                min_shared_tokens=args.min_shared_tokens,
            )
        )

    if args.uthmani_path.exists():
        uthmani_rows = load_quran_passage_dataset(args.uthmani_path)
        all_records.extend(
            _build_runtime_neighbors(
                matching_corpus="uthmani",
                rows=uthmani_rows,
                max_window_size=args.max_window_size,
                top_k=args.top_k,
                min_shared_tokens=args.min_shared_tokens,
            )
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(all_records)} source rows to {args.output}")


if __name__ == "__main__":
    main()
