from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_quran_canonical(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Canonical Uthmani Quran CSV not found: {csv_path}")

    rows: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["window_size"] = int(row.get("window_size") or 0) if row.get("window_size") else 0
            row["surah_no"] = int(row["surah_no"])
            row["ayah_no"] = int(row["ayah_no"])
            row["translation_name"] = row.get("translation_name") or ""
            row["bismillah"] = row.get("bismillah") or ""
            row["text_normalized_light"] = row.get("text_normalized_light") or ""
            row["text_normalized_aggressive"] = row.get("text_normalized_aggressive") or ""
            rows.append(row)
    if not rows:
        raise ValueError("No canonical Uthmani Quran rows found.")
    return rows


def group_by_surah(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["surah_no"]].append(row)
    for surah_no in grouped:
        grouped[surah_no].sort(key=lambda r: r["ayah_no"])
    return dict(grouped)


def build_window_record(window_rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = window_rows[0]
    last = window_rows[-1]
    surah_no = first["surah_no"]
    start_ayah = first["ayah_no"]
    end_ayah = last["ayah_no"]
    surah_name_ar = first["surah_name_ar"]
    window_size = len(window_rows)

    text_display = " ".join(r["text_display"].strip() for r in window_rows if r["text_display"].strip())
    text_normalized_light = " ".join(r["text_normalized_light"].strip() for r in window_rows if r["text_normalized_light"].strip())
    text_normalized_aggressive = " ".join(r["text_normalized_aggressive"].strip() for r in window_rows if r["text_normalized_aggressive"].strip())

    component_citations = [r["citation_string"] for r in window_rows]
    component_source_ids = [r["canonical_source_id"] for r in window_rows]

    return {
        "source_id": "QUR-AR-TANZIL-UTHMANI-PASSAGE-001",
        "source_type": "quran_passage",
        "language": "ar",
        "translation_name": "",
        "window_size": window_size,
        "surah_no": surah_no,
        "start_ayah": start_ayah,
        "end_ayah": end_ayah,
        "surah_name_ar": surah_name_ar,
        "text_display": text_display,
        "text_normalized_light": text_normalized_light,
        "text_normalized_aggressive": text_normalized_aggressive,
        "canonical_source_id": f"quran_passage:{surah_no}:{start_ayah}-{end_ayah}:ar",
        "citation_string": f"Quran {surah_no}:{start_ayah}-{end_ayah}",
        "component_citations_json": json.dumps(component_citations, ensure_ascii=False),
        "component_source_ids_json": json.dumps(component_source_ids, ensure_ascii=False),
    }


def generate_passage_windows(canonical_rows: list[dict[str, Any]], window_sizes: list[int]) -> list[dict[str, Any]]:
    grouped = group_by_surah(canonical_rows)
    passage_rows: list[dict[str, Any]] = []
    for _, surah_rows in grouped.items():
        ayah_count = len(surah_rows)
        for window_size in window_sizes:
            if window_size < 2 or ayah_count < window_size:
                continue
            for start_idx in range(0, ayah_count - window_size + 1):
                passage_rows.append(build_window_record(surah_rows[start_idx : start_idx + window_size]))
    return passage_rows


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_id",
        "source_type",
        "language",
        "translation_name",
        "window_size",
        "surah_no",
        "start_ayah",
        "end_ayah",
        "surah_name_ar",
        "text_display",
        "text_normalized_light",
        "text_normalized_aggressive",
        "canonical_source_id",
        "citation_string",
        "component_citations_json",
        "component_source_ids_json",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate derived Uthmani Quran passage windows from canonical ayah rows.")
    parser.add_argument(
        "--input",
        type=str,
        default="data/processed/quran_uthmani/quran_arabic_uthmani_canonical.csv",
        help="Path to canonical Uthmani Quran CSV.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="data/processed/quran_uthmani_passages",
        help="Directory for derived Uthmani passage outputs.",
    )
    parser.add_argument(
        "--window-sizes",
        type=str,
        default="2,3,4",
        help="Comma-separated window sizes to generate. Example: 2,3,4",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.out_dir)
    window_sizes = [int(x.strip()) for x in args.window_sizes.split(",") if x.strip()]

    canonical_rows = load_quran_canonical(input_path)
    passage_rows = generate_passage_windows(canonical_rows, window_sizes=window_sizes)

    csv_path = out_dir / "quran_uthmani_passage_windows_v1.csv"
    jsonl_path = out_dir / "quran_uthmani_passage_windows_v1.jsonl"
    summary_path = out_dir / "quran_uthmani_passage_windows_v1_summary.json"

    write_csv(passage_rows, csv_path)
    write_jsonl(passage_rows, jsonl_path)
    summary = {
        "total_windows": len(passage_rows),
        "counts_by_window_size": {
            str(size): sum(1 for row in passage_rows if int(row["window_size"]) == size)
            for size in sorted(window_sizes)
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("Uthmani Quran passage window generation complete.")
    print(f"CSV:     {csv_path}")
    print(f"JSONL:   {jsonl_path}")
    print(f"Summary: {summary_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
