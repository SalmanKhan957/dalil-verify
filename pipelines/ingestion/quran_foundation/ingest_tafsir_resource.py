from __future__ import annotations

import argparse
import json
from pathlib import Path

from domains.tafsir.ingestion.ingest_resource import ingest_resource
from domains.tafsir.types import SourceWorkSeed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize and ingest a raw Quran Foundation tafsir snapshot into PostgreSQL.")
    parser.add_argument("--resource-id", type=int, required=True, help="Quran Foundation resource id.")
    parser.add_argument("--source-dir", type=Path, required=True, help="Directory containing chapter_*.json files.")
    parser.add_argument("--work-slug", type=str, required=True, help="Stable DALIL work slug, for example ibn-kathir-en.")
    parser.add_argument("--display-name", type=str, required=True, help="Human-readable source work display name.")
    parser.add_argument("--citation-label", type=str, default="Tafsir Ibn Kathir", help="Citation label used in answer rendering.")
    parser.add_argument("--author-name", type=str, default="Ibn Kathir", help="Author name for source metadata.")
    parser.add_argument("--language-code", type=str, default="en", help="DALIL language code for the tafsir work.")
    parser.add_argument("--upstream-provider", type=str, default="quran_foundation", help="Upstream provider slug.")
    parser.add_argument("--enable-source", action="store_true", help="Enable this source work for answering after ingestion.")
    parser.add_argument("--default-for-explain", action="store_true", help="Mark this source work as the default Tafsir for explain-mode requests.")
    parser.add_argument("--supports-quran-composition", action="store_true", help="Allow this Tafsir work to be composed with Quran evidence.")
    parser.add_argument("--priority-rank", type=int, default=1000, help="Lower numbers win when selecting between multiple approved Tafsir works.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_id = f"tafsir:{args.work_slug}"
    seed = SourceWorkSeed(
        source_domain="tafsir",
        work_slug=args.work_slug,
        source_id=source_id,
        display_name=args.display_name,
        citation_label=args.citation_label,
        author_name=args.author_name,
        language_code=args.language_code,
        source_kind="commentary",
        upstream_provider=args.upstream_provider,
        upstream_resource_id=args.resource_id,
        enabled=args.enable_source,
        approved_for_answering=args.enable_source,
        default_for_explain=args.default_for_explain,
        supports_quran_composition=args.supports_quran_composition,
        priority_rank=args.priority_rank,
        version_label=None,
        policy_note="",
        metadata_json={},
    )
    summary = ingest_resource(source_dir=args.source_dir, resource_id=args.resource_id, work_seed=seed)
    print(
        json.dumps(
            {
                "run_id": summary.run_id,
                "status": summary.status,
                "chapters_seen": summary.chapters_seen,
                "raw_rows_seen": summary.raw_rows_seen,
                "sections_built": summary.sections_built,
                "inserted_count": summary.inserted_count,
                "updated_count": summary.updated_count,
                "skipped_count": summary.skipped_count,
                "failed_count": summary.failed_count,
                "notes_json": summary.notes_json,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
