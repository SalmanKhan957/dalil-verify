from __future__ import annotations

import argparse
import json
from pathlib import Path

from domains.tafsir.ingestion.ingest_pre_normalized import ingest_pre_normalized_sections
from domains.tafsir.ingestion.tafheem_normalizer import normalize_tafheem_file
from domains.tafsir.types import SourceWorkSeed


DEFAULT_EXTERNAL_RESOURCE_ID = 817001



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize and ingest Tafheem al-Quran JSON into canonical tafsir storage.")
    parser.add_argument("--source-file", type=Path, required=True, help="Path to Tafheem al-Quran JSON file.")
    parser.add_argument("--work-slug", type=str, default="tafheem-al-quran-en", help="Stable DALIL work slug.")
    parser.add_argument("--display-name", type=str, default="Tafheem al-Quran", help="Human-readable display name.")
    parser.add_argument("--citation-label", type=str, default="Tafheem al-Quran", help="Citation label for answer rendering.")
    parser.add_argument("--author-name", type=str, default="Abul A'la Maududi", help="Author/source author label.")
    parser.add_argument("--language-code", type=str, default="en", help="DALIL language code.")
    parser.add_argument("--upstream-provider", type=str, default="external_tafheem_json", help="Upstream provider slug.")
    parser.add_argument("--external-resource-id", type=int, default=DEFAULT_EXTERNAL_RESOURCE_ID, help="Synthetic upstream resource id used for DB uniqueness and provenance.")
    parser.add_argument("--enable-source", action="store_true", help="Enable this tafsir source for answering.")
    parser.add_argument("--default-for-explain", action="store_true", help="Mark as default explain tafsir.")
    parser.add_argument("--supports-quran-composition", action="store_true", help="Allow composition with Quran evidence.")
    parser.add_argument("--priority-rank", type=int, default=300, help="Source priority rank; lower wins.")
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    source_id = f"tafsir:{args.work_slug}"
    normalized_sections = normalize_tafheem_file(
        source_file=args.source_file,
        source_id=source_id,
        upstream_provider=args.upstream_provider,
        upstream_resource_id=args.external_resource_id,
        language_code=args.language_code,
    )
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
        upstream_resource_id=args.external_resource_id,
        enabled=args.enable_source,
        approved_for_answering=args.enable_source,
        default_for_explain=args.default_for_explain,
        supports_quran_composition=args.supports_quran_composition,
        priority_rank=args.priority_rank,
        version_label=None,
        policy_note="",
        metadata_json={"source_file": str(args.source_file.as_posix()), "format": "surah_ayah_t_field"},
    )
    summary = ingest_pre_normalized_sections(
        source_root=args.source_file,
        resource_id=args.external_resource_id,
        work_seed=seed,
        normalized_sections=normalized_sections,
    )
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
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
