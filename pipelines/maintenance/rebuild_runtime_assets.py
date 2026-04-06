from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from domains.quran.repositories.runtime_assets_repository import (
    ASSET_FILE_MAP,
    LEGACY_ASSET_PATHS,
    build_runtime_manifest_for_bundle,
    get_runtime_artifact_root,
    get_runtime_artifact_version,
    write_runtime_manifest,
)


def rebuild_runtime_assets(*, output_root: Path | None = None, version: str | None = None, builder: str = "pipelines.maintenance.rebuild_runtime_assets") -> Path:
    resolved_root = output_root or get_runtime_artifact_root()
    resolved_version = version or get_runtime_artifact_version()
    bundle_dir = resolved_root / resolved_version
    bundle_dir.mkdir(parents=True, exist_ok=True)

    for asset_key, source_path in LEGACY_ASSET_PATHS.items():
        if not source_path.exists():
            raise FileNotFoundError(f"Legacy runtime source missing for {asset_key}: {source_path}")
        target_path = bundle_dir / ASSET_FILE_MAP[asset_key]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    manifest = build_runtime_manifest_for_bundle(bundle_dir, version=resolved_version, builder=builder)
    write_runtime_manifest(bundle_dir, manifest)
    return bundle_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a versioned Quran runtime artifact bundle from legacy processed assets.")
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--version", type=str, default=None)
    args = parser.parse_args()
    print(rebuild_runtime_assets(output_root=args.output_root, version=args.version))


if __name__ == "__main__":
    main()
