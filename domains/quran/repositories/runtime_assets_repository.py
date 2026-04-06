from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from infrastructure.config.settings import settings

REPO_ROOT = Path(__file__).resolve().parents[3]
LEGACY_QURAN_ARABIC_PATH = REPO_ROOT / "data/processed/quran/quran_arabic_canonical.csv"
LEGACY_QURAN_PASSAGE_DATA_PATH = REPO_ROOT / "data/processed/quran_passages/quran_passage_windows_v1.csv"
LEGACY_QURAN_UTHMANI_DATA_PATH = REPO_ROOT / "data/processed/quran_uthmani/quran_arabic_uthmani_canonical.csv"
LEGACY_QURAN_UTHMANI_PASSAGE_DATA_PATH = REPO_ROOT / "data/processed/quran_uthmani_passages/quran_uthmani_passage_windows_v1.csv"
LEGACY_QURAN_TRANSLATION_PATH = REPO_ROOT / "data/processed/quran_translations/quran_en_single_translation.csv"
LEGACY_QURAN_PASSAGE_NEIGHBOR_INDEX_PATH = REPO_ROOT / "data/processed/quran_passage_neighbors/passage_neighbors_v1.jsonl"

DEFAULT_RUNTIME_ARTIFACT_ROOT = settings.quran_runtime_artifact_root
DEFAULT_RUNTIME_ARTIFACT_VERSION = settings.quran_runtime_artifact_version
DEFAULT_RUNTIME_REQUIRE_BUNDLE = settings.quran_runtime_require_bundle
DEFAULT_RUNTIME_PREFER_BUNDLE = settings.quran_runtime_prefer_bundle
DEFAULT_RUNTIME_MANIFEST_FILENAME = "manifest.json"

DEFAULT_QURAN_ARABIC_PATH = LEGACY_QURAN_ARABIC_PATH
DEFAULT_QURAN_PASSAGE_DATA_PATH = LEGACY_QURAN_PASSAGE_DATA_PATH
DEFAULT_QURAN_UTHMANI_DATA_PATH = LEGACY_QURAN_UTHMANI_DATA_PATH
DEFAULT_QURAN_UTHMANI_PASSAGE_DATA_PATH = LEGACY_QURAN_UTHMANI_PASSAGE_DATA_PATH
DEFAULT_QURAN_TRANSLATION_PATH = LEGACY_QURAN_TRANSLATION_PATH
DEFAULT_QURAN_PASSAGE_NEIGHBOR_INDEX_PATH = LEGACY_QURAN_PASSAGE_NEIGHBOR_INDEX_PATH

RuntimeLabel = Literal["simple", "uthmani"]
RuntimeArtifactSource = Literal["runtime_bundle", "legacy_processed_fallback"]


class RuntimeArtifactError(RuntimeError):
    """Raised when runtime artifact resolution or validation fails."""


@dataclass(frozen=True, slots=True)
class QuranRuntimeArtifactBundle:
    version: str
    source: RuntimeArtifactSource
    root_dir: Path
    manifest_path: Path | None
    quran_arabic_path: Path
    quran_passage_path: Path
    quran_uthmani_path: Path
    quran_uthmani_passage_path: Path
    quran_translation_path: Path
    quran_passage_neighbor_index_path: Path
    manifest: dict[str, Any]

    def describe(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source": self.source,
            "root_dir": str(self.root_dir),
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "quran_arabic_path": str(self.quran_arabic_path),
            "quran_passage_path": str(self.quran_passage_path),
            "quran_uthmani_path": str(self.quran_uthmani_path),
            "quran_uthmani_passage_path": str(self.quran_uthmani_passage_path),
            "quran_translation_path": str(self.quran_translation_path),
            "quran_passage_neighbor_index_path": str(self.quran_passage_neighbor_index_path),
        }


ASSET_FILE_MAP = {
    "quran_arabic": "quran/quran_arabic_canonical.csv",
    "quran_passage": "quran_passages/quran_passage_windows_v1.csv",
    "quran_uthmani": "quran_uthmani/quran_arabic_uthmani_canonical.csv",
    "quran_uthmani_passage": "quran_uthmani_passages/quran_uthmani_passage_windows_v1.csv",
    "quran_translation_en": "quran_translations/quran_en_single_translation.csv",
    "quran_passage_neighbors": "quran_passage_neighbors/passage_neighbors_v1.jsonl",
}

LEGACY_ASSET_PATHS = {
    "quran_arabic": LEGACY_QURAN_ARABIC_PATH,
    "quran_passage": LEGACY_QURAN_PASSAGE_DATA_PATH,
    "quran_uthmani": LEGACY_QURAN_UTHMANI_DATA_PATH,
    "quran_uthmani_passage": LEGACY_QURAN_UTHMANI_PASSAGE_DATA_PATH,
    "quran_translation_en": LEGACY_QURAN_TRANSLATION_PATH,
    "quran_passage_neighbors": LEGACY_QURAN_PASSAGE_NEIGHBOR_INDEX_PATH,
}


def _truthy_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_runtime_artifact_root() -> Path:
    raw = os.getenv("DALIL_QURAN_RUNTIME_ARTIFACT_ROOT")
    return Path(raw).expanduser().resolve() if raw else DEFAULT_RUNTIME_ARTIFACT_ROOT


def get_runtime_artifact_version() -> str:
    return os.getenv("DALIL_QURAN_RUNTIME_ARTIFACT_VERSION", DEFAULT_RUNTIME_ARTIFACT_VERSION).strip() or "v1"


def get_runtime_bundle_dir(*, version: str | None = None, artifact_root: Path | None = None) -> Path:
    return (artifact_root or get_runtime_artifact_root()) / (version or get_runtime_artifact_version())


def get_runtime_manifest_path(*, version: str | None = None, artifact_root: Path | None = None) -> Path:
    return get_runtime_bundle_dir(version=version, artifact_root=artifact_root) / DEFAULT_RUNTIME_MANIFEST_FILENAME


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def count_data_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig") as f:
        line_count = sum(1 for _ in f)
    return line_count if path.suffix.lower() == ".jsonl" else max(0, line_count - 1)


def build_runtime_manifest_for_bundle(bundle_dir: Path, *, version: str, builder: str) -> dict[str, Any]:
    assets: dict[str, dict[str, Any]] = {}
    for asset_key, relative_path in ASSET_FILE_MAP.items():
        asset_path = bundle_dir / relative_path
        if not asset_path.exists():
            raise RuntimeArtifactError(f"Missing runtime asset for manifest build: {asset_path}")
        assets[asset_key] = {
            "relative_path": relative_path,
            "sha256": compute_sha256(asset_path),
            "row_count": count_data_rows(asset_path),
            "size_bytes": asset_path.stat().st_size,
        }
    return {
        "artifact_family": "quran_runtime",
        "manifest_version": 1,
        "artifact_version": version,
        "builder": builder,
        "asset_count": len(assets),
        "assets": assets,
    }


def write_runtime_manifest(bundle_dir: Path, manifest: dict[str, Any]) -> Path:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = bundle_dir / DEFAULT_RUNTIME_MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def load_runtime_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeArtifactError(f"Quran runtime manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeArtifactError(f"Invalid Quran runtime manifest JSON at: {manifest_path}") from exc
    if not isinstance(manifest, dict):
        raise RuntimeArtifactError("Quran runtime manifest payload must be a JSON object.")
    if str(manifest.get("artifact_family") or "") != "quran_runtime":
        raise RuntimeArtifactError('Quran runtime manifest artifact_family must be "quran_runtime".')
    if not isinstance(manifest.get("assets"), dict):
        raise RuntimeArtifactError("Quran runtime manifest must include an assets object.")
    return manifest


def validate_runtime_manifest(manifest: dict[str, Any], *, bundle_dir: Path) -> None:
    assets = manifest.get("assets") or {}
    missing = [key for key in ASSET_FILE_MAP if key not in assets]
    if missing:
        raise RuntimeArtifactError(f"Quran runtime manifest missing asset entries: {', '.join(sorted(missing))}")
    for asset_key, expected_relative_path in ASSET_FILE_MAP.items():
        entry = assets[asset_key]
        actual_relative_path = str(entry.get("relative_path") or "")
        if actual_relative_path != expected_relative_path:
            raise RuntimeArtifactError(
                f"Quran runtime manifest asset {asset_key!r} points to {actual_relative_path!r}; expected {expected_relative_path!r}."
            )
        asset_path = bundle_dir / actual_relative_path
        if not asset_path.exists():
            raise RuntimeArtifactError(f"Quran runtime asset missing on disk: {asset_path}")
        expected_sha = str(entry.get("sha256") or "")
        if expected_sha and compute_sha256(asset_path) != expected_sha:
            raise RuntimeArtifactError(f"Checksum mismatch for Quran runtime asset {asset_key!r}.")
        expected_rows = entry.get("row_count")
        if expected_rows is not None and count_data_rows(asset_path) != int(expected_rows):
            raise RuntimeArtifactError(f"Row-count mismatch for Quran runtime asset {asset_key!r}.")


def _build_bundle_from_manifest(*, bundle_dir: Path, manifest_path: Path, manifest: dict[str, Any]) -> QuranRuntimeArtifactBundle:
    assets = manifest["assets"]
    return QuranRuntimeArtifactBundle(
        version=str(manifest.get("artifact_version") or bundle_dir.name),
        source="runtime_bundle",
        root_dir=bundle_dir,
        manifest_path=manifest_path,
        quran_arabic_path=bundle_dir / assets["quran_arabic"]["relative_path"],
        quran_passage_path=bundle_dir / assets["quran_passage"]["relative_path"],
        quran_uthmani_path=bundle_dir / assets["quran_uthmani"]["relative_path"],
        quran_uthmani_passage_path=bundle_dir / assets["quran_uthmani_passage"]["relative_path"],
        quran_translation_path=bundle_dir / assets["quran_translation_en"]["relative_path"],
        quran_passage_neighbor_index_path=bundle_dir / assets["quran_passage_neighbors"]["relative_path"],
        manifest=manifest,
    )


def _safe_relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")

def _build_legacy_bundle() -> QuranRuntimeArtifactBundle:
    missing = [name for name, path in LEGACY_ASSET_PATHS.items() if not path.exists()]
    if missing:
        raise RuntimeArtifactError("Legacy Quran processed assets are missing: " + ", ".join(sorted(missing)))
    manifest = {
        "artifact_family": "quran_runtime",
        "manifest_version": 1,
        "artifact_version": "legacy-processed",
        "builder": "legacy_processed_fallback",
        "asset_count": len(LEGACY_ASSET_PATHS),
        "assets": {
            key: {
                "relative_path": _safe_relative_path(path),
                "sha256": compute_sha256(path),
                "row_count": count_data_rows(path),
                "size_bytes": path.stat().st_size,
            }
            for key, path in LEGACY_ASSET_PATHS.items()
        },
    }
    return QuranRuntimeArtifactBundle(
        version="legacy-processed",
        source="legacy_processed_fallback",
        root_dir=REPO_ROOT / "data/processed",
        manifest_path=None,
        quran_arabic_path=LEGACY_QURAN_ARABIC_PATH,
        quran_passage_path=LEGACY_QURAN_PASSAGE_DATA_PATH,
        quran_uthmani_path=LEGACY_QURAN_UTHMANI_DATA_PATH,
        quran_uthmani_passage_path=LEGACY_QURAN_UTHMANI_PASSAGE_DATA_PATH,
        quran_translation_path=LEGACY_QURAN_TRANSLATION_PATH,
        quran_passage_neighbor_index_path=LEGACY_QURAN_PASSAGE_NEIGHBOR_INDEX_PATH,
        manifest=manifest,
    )


def resolve_runtime_artifact_bundle(*, artifact_root: Path | None = None, version: str | None = None, require_bundle: bool | None = None, prefer_bundle: bool | None = None) -> QuranRuntimeArtifactBundle:
    resolved_root = artifact_root or get_runtime_artifact_root()
    resolved_version = version or get_runtime_artifact_version()
    resolved_require_bundle = _truthy_env("DALIL_QURAN_RUNTIME_REQUIRE_BUNDLE", DEFAULT_RUNTIME_REQUIRE_BUNDLE if require_bundle is None else require_bundle)
    resolved_prefer_bundle = _truthy_env("DALIL_QURAN_RUNTIME_PREFER_BUNDLE", DEFAULT_RUNTIME_PREFER_BUNDLE if prefer_bundle is None else prefer_bundle)
    bundle_dir = resolved_root / resolved_version
    manifest_path = bundle_dir / DEFAULT_RUNTIME_MANIFEST_FILENAME
    if resolved_prefer_bundle and manifest_path.exists():
        manifest = load_runtime_manifest(manifest_path)
        validate_runtime_manifest(manifest, bundle_dir=bundle_dir)
        return _build_bundle_from_manifest(bundle_dir=bundle_dir, manifest_path=manifest_path, manifest=manifest)
    if resolved_require_bundle:
        if manifest_path.exists():
            manifest = load_runtime_manifest(manifest_path)
            validate_runtime_manifest(manifest, bundle_dir=bundle_dir)
            return _build_bundle_from_manifest(bundle_dir=bundle_dir, manifest_path=manifest_path, manifest=manifest)
        raise RuntimeArtifactError(f"Quran runtime artifact bundle required but manifest not found at: {manifest_path}")
    return _build_legacy_bundle()


def inspect_runtime_artifact_bundle(*, artifact_root: Path | None = None, version: str | None = None, require_bundle: bool | None = None, prefer_bundle: bool | None = None) -> dict[str, Any]:
    try:
        bundle = resolve_runtime_artifact_bundle(artifact_root=artifact_root, version=version, require_bundle=require_bundle, prefer_bundle=prefer_bundle)
    except RuntimeArtifactError as exc:
        return {
            "checked": True,
            "ok": False,
            "issue_count": 1,
            "warning_count": 0,
            "error_count": 1,
            "issues": [{"code": "quran_runtime_artifact_unavailable", "message": str(exc), "severity": "error"}],
        }
    return {
        "checked": True,
        "ok": True,
        "issue_count": 0,
        "warning_count": 0,
        "error_count": 0,
        "source": bundle.source,
        "version": bundle.version,
        "root_dir": str(bundle.root_dir),
        "manifest_path": str(bundle.manifest_path) if bundle.manifest_path else None,
        "assets": bundle.describe(),
    }


def get_quran_path(*, label: RuntimeLabel = "simple") -> Path:
    bundle = resolve_runtime_artifact_bundle()
    return bundle.quran_uthmani_path if label == "uthmani" else bundle.quran_arabic_path


def get_passage_path(*, label: RuntimeLabel = "simple") -> Path:
    bundle = resolve_runtime_artifact_bundle()
    return bundle.quran_uthmani_passage_path if label == "uthmani" else bundle.quran_passage_path
