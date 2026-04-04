from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from services.quran_foundation_client import (
    QuranFoundationContentClient,
    QuranFoundationSettings,
    QuranFoundationTafsirAPI,
)
from infrastructure.clients.quran_foundation.tafsir_api import TafsirChapterNotFoundError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download raw tafsir payloads from Quran Foundation and snapshot them locally.",
    )
    parser.add_argument("--resource-id", type=int, required=True, help="Quran Foundation tafsir resource id.")
    parser.add_argument(
        "--chapters",
        type=str,
        default="all",
        help="Comma-separated chapter numbers or 'all'. Example: 1,2,36",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=50,
        help="Page size for chapter tafsir pagination.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/quran_foundation/tafsir"),
        help="Root output directory for raw snapshots.",
    )
    parser.add_argument(
        "--best-effort",
        action="store_true",
        help="Skip missing chapters (HTTP 404), record them in the manifest, and continue.",
    )
    return parser.parse_args()


def _resolve_chapters(chapters_arg: str) -> list[int]:
    if chapters_arg.strip().lower() == "all":
        return list(range(1, 115))
    chapters = []
    for part in chapters_arg.split(","):
        value = int(part.strip())
        if not 1 <= value <= 114:
            raise ValueError(f"Chapter number must be between 1 and 114, got {value}.")
        chapters.append(value)
    return chapters


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> None:
    args = parse_args()
    settings = QuranFoundationSettings.from_env()
    chapters = _resolve_chapters(args.chapters)
    root_dir = args.output_dir / f"resource_{args.resource_id}"
    root_dir.mkdir(parents=True, exist_ok=True)

    with QuranFoundationContentClient.from_settings(settings) as client:
        tafsir_api = QuranFoundationTafsirAPI(client)
        manifest: dict[str, object] = {
            "resource_id": args.resource_id,
            "environment": settings.environment,
            "chapters_requested": chapters,
            "per_page": args.per_page,
            "mode": "best_effort" if args.best_effort else "strict",
            "started_at": _utc_now_iso(),
            "downloaded_files": [],
            "downloaded_chapters": [],
            "missing_chapters": [],
            "failed_chapters": [],
        }

        try:
            for chapter_number in chapters:
                try:
                    items = list(
                        tafsir_api.iter_surah_tafsirs(
                            resource_id=args.resource_id,
                            chapter_number=chapter_number,
                            per_page=args.per_page,
                        )
                    )
                except TafsirChapterNotFoundError as exc:
                    if args.best_effort:
                        print(f"Skipping missing chapter {chapter_number}: {exc}")
                        manifest["missing_chapters"].append(chapter_number)
                        continue
                    raise
                except httpx.HTTPStatusError as exc:
                    manifest["failed_chapters"].append(
                        {
                            "chapter_number": chapter_number,
                            "status_code": exc.response.status_code if exc.response is not None else None,
                            "message": str(exc),
                        }
                    )
                    raise
                except Exception as exc:  # pragma: no cover - defensive runtime capture
                    manifest["failed_chapters"].append(
                        {
                            "chapter_number": chapter_number,
                            "status_code": None,
                            "message": str(exc),
                        }
                    )
                    raise

                payload = {
                    "resource_id": args.resource_id,
                    "chapter_number": chapter_number,
                    "count": len(items),
                    "tafsirs": [item.raw for item in items],
                }
                out_path = root_dir / f"chapter_{chapter_number}.json"
                out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                manifest["downloaded_files"].append(str(out_path.as_posix()))
                manifest["downloaded_chapters"].append(chapter_number)
                print(f"Wrote {len(items)} tafsir entries -> {out_path}")
        finally:
            manifest["finished_at"] = _utc_now_iso()
            manifest_path = root_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Manifest written -> {manifest_path}")


if __name__ == "__main__":
    main()
