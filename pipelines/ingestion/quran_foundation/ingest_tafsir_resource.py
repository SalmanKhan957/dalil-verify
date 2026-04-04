from __future__ import annotations

import argparse
import json
from pathlib import Path

from infrastructure.db.session import get_session
from domains.tafsir.normalizer import normalize_resource_directory
from services.tafsir.repository import SqlAlchemyTafsirRepository
from services.tafsir.types import SourceWorkSeed, TafsirIngestionChapterResult, TafsirIngestionRunSummary


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


def ingest_resource(
    *,
    source_dir: Path,
    resource_id: int,
    work_seed: SourceWorkSeed,
) -> TafsirIngestionRunSummary:
    normalized_sections = normalize_resource_directory(
        source_dir=source_dir,
        expected_resource_id=resource_id,
        source_id=work_seed.source_id,
        upstream_provider=work_seed.upstream_provider,
        language_code=work_seed.language_code,
    )

    with get_session() as session:
        repository = SqlAlchemyTafsirRepository(session)
        work = repository.upsert_source_work(work_seed)
        run = repository.open_ingestion_run(work_id=work.id, resource_id=resource_id, source_root=source_dir)

        notes: dict[str, object] = {"work_slug": work.work_slug, "source_dir": str(source_dir.as_posix())}
        status = "completed"
        for chapter_number, sections in normalized_sections.items():
            warnings: list[str] = []
            counts = repository.bulk_upsert_tafsir_sections(work_id=work.id, sections=sections)
            result = TafsirIngestionChapterResult(
                chapter_number=chapter_number,
                raw_rows_seen=len({section.anchor_verse_key for section in sections}) + sum(
                    max(0, section.ayah_end - section.ayah_start) for section in sections
                ),
                sections_built=len(sections),
                inserted_count=counts["inserted"],
                updated_count=counts["updated"],
                skipped_count=counts["skipped"],
                failed_count=0,
                warnings=warnings,
            )
            repository.record_chapter_result(run_id=run.run_id, result=result)

        return repository.finalize_ingestion_run(run_id=run.run_id, status=status, notes_json=notes)


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
        policy_note="Approved bounded Tafsir source for Quran span explanation and commentary-backed answer composition." if args.enable_source else None,
        metadata_json={"ingested_from": "raw_quran_foundation_snapshot"},
    )
    summary = ingest_resource(source_dir=args.source_dir, resource_id=args.resource_id, work_seed=seed)
    print(json.dumps(summary.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
