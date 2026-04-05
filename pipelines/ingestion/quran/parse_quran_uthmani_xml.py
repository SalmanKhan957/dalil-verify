from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from shared.utils.arabic_text import normalize_arabic_aggressive, normalize_arabic_light


def build_quran_rows(xml_path: Path) -> list[dict]:
    if not xml_path.exists():
        raise FileNotFoundError(f"Input XML not found: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    if root.tag != "quran":
        raise ValueError(f"Unexpected root tag: {root.tag}")

    rows: list[dict] = []
    for sura in root.findall("sura"):
        surah_no = int(sura.attrib["index"])
        surah_name_ar = sura.attrib.get("name", "").strip()
        for aya in sura.findall("aya"):
            ayah_no = int(aya.attrib["index"])
            text_display = aya.attrib.get("text", "").strip()
            bismillah = aya.attrib.get("bismillah", "").strip()
            rows.append(
                {
                    "source_id": "QUR-AR-TANZIL-UTHMANI-001",
                    "source_type": "quran",
                    "language": "ar",
                    "translation_name": "",
                    "surah_no": surah_no,
                    "ayah_no": ayah_no,
                    "surah_name_ar": surah_name_ar,
                    "text_display": text_display,
                    "text_normalized_light": normalize_arabic_light(text_display),
                    "text_normalized_aggressive": normalize_arabic_aggressive(text_display),
                    "bismillah": bismillah,
                    "canonical_source_id": f"quran:{surah_no}:{ayah_no}:ar",
                    "citation_string": f"Quran {surah_no}:{ayah_no}",
                }
            )

    if not rows:
        raise ValueError("No ayah rows were parsed from the Uthmani XML file.")

    return rows


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_id",
        "source_type",
        "language",
        "translation_name",
        "surah_no",
        "ayah_no",
        "surah_name_ar",
        "text_display",
        "text_normalized_light",
        "text_normalized_aggressive",
        "bismillah",
        "canonical_source_id",
        "citation_string",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse Uthmani Quran XML into canonical CSV and JSONL datasets.")
    parser.add_argument(
        "--input",
        type=str,
        default="data/raw/quran/tanzil/quran-uthmani.xml",
        help="Path to the source Uthmani XML file.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="data/processed/quran_uthmani",
        help="Directory where processed Uthmani files will be written.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.out_dir)
    rows = build_quran_rows(input_path)

    csv_path = out_dir / "quran_arabic_uthmani_canonical.csv"
    jsonl_path = out_dir / "quran_arabic_uthmani_canonical.jsonl"

    write_csv(rows, csv_path)
    write_jsonl(rows, jsonl_path)

    print("Uthmani Quran parsing complete.")
    print(f"Rows written: {len(rows)}")
    print(f"CSV:   {csv_path}")
    print(f"JSONL: {jsonl_path}")


if __name__ == "__main__":
    main()
