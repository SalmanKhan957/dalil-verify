from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

repo = importlib.import_module("domains.quran.repositories.runtime_assets_repository")


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_bundle(tmp_path: Path, *, version: str = "vtest") -> tuple[Path, Path]:
    bundle_dir = tmp_path / version
    _write_file(bundle_dir / "quran/quran_arabic_canonical.csv", "surah_no,ayah_no,text_display\n1,1,abc\n")
    _write_file(bundle_dir / "quran_passages/quran_passage_windows_v1.csv", "window_size,surah_no,start_ayah,end_ayah,text_display\n2,1,1,2,abc\n")
    _write_file(bundle_dir / "quran_uthmani/quran_arabic_uthmani_canonical.csv", "surah_no,ayah_no,text_display\n1,1,abc\n")
    _write_file(bundle_dir / "quran_uthmani_passages/quran_uthmani_passage_windows_v1.csv", "window_size,surah_no,start_ayah,end_ayah,text_display\n2,1,1,2,abc\n")
    _write_file(bundle_dir / "quran_translations/quran_en_single_translation.csv", "surah_no,ayah_no,text\n1,1,In the name\n")
    _write_file(bundle_dir / "quran_passage_neighbors/passage_neighbors_v1.jsonl", json.dumps({"matching_corpus": "simple", "source_canonical_id": "quran_passage:1:1-2:ar", "window_size": 2, "neighbors": []}) + "\n")
    manifest = repo.build_runtime_manifest_for_bundle(bundle_dir, version=version, builder="test")
    manifest_path = repo.write_runtime_manifest(bundle_dir, manifest)
    return bundle_dir, manifest_path


def test_resolve_runtime_artifact_bundle_prefers_manifest_bundle(tmp_path: Path) -> None:
    _build_bundle(tmp_path, version="v2")
    bundle = repo.resolve_runtime_artifact_bundle(artifact_root=tmp_path, version="v2", require_bundle=True, prefer_bundle=True)
    assert bundle.source == "runtime_bundle"
    assert bundle.version == "v2"
    assert bundle.manifest_path == tmp_path / "v2" / "manifest.json"


def test_validate_runtime_manifest_rejects_checksum_mismatch(tmp_path: Path) -> None:
    bundle_dir, manifest_path = _build_bundle(tmp_path, version="v3")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["assets"]["quran_arabic"]["sha256"] = "bad"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded = repo.load_runtime_manifest(manifest_path)
    with pytest.raises(repo.RuntimeArtifactError):
        repo.validate_runtime_manifest(loaded, bundle_dir=bundle_dir)


def test_resolve_runtime_artifact_bundle_falls_back_to_legacy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_legacy_root = tmp_path / "legacy"
    _write_file(fake_legacy_root / "quran/quran_arabic_canonical.csv", "surah_no,ayah_no,text_display\n1,1,abc\n")
    _write_file(fake_legacy_root / "quran_passages/quran_passage_windows_v1.csv", "window_size,surah_no,start_ayah,end_ayah,text_display\n2,1,1,2,abc\n")
    _write_file(fake_legacy_root / "quran_uthmani/quran_arabic_uthmani_canonical.csv", "surah_no,ayah_no,text_display\n1,1,abc\n")
    _write_file(fake_legacy_root / "quran_uthmani_passages/quran_uthmani_passage_windows_v1.csv", "window_size,surah_no,start_ayah,end_ayah,text_display\n2,1,1,2,abc\n")
    _write_file(fake_legacy_root / "quran_translations/quran_en_single_translation.csv", "surah_no,ayah_no,text\n1,1,In the name\n")
    _write_file(fake_legacy_root / "quran_passage_neighbors/passage_neighbors_v1.jsonl", "{}\n")

    monkeypatch.setattr(repo, "LEGACY_QURAN_ARABIC_PATH", fake_legacy_root / "quran/quran_arabic_canonical.csv")
    monkeypatch.setattr(repo, "LEGACY_QURAN_PASSAGE_DATA_PATH", fake_legacy_root / "quran_passages/quran_passage_windows_v1.csv")
    monkeypatch.setattr(repo, "LEGACY_QURAN_UTHMANI_DATA_PATH", fake_legacy_root / "quran_uthmani/quran_arabic_uthmani_canonical.csv")
    monkeypatch.setattr(repo, "LEGACY_QURAN_UTHMANI_PASSAGE_DATA_PATH", fake_legacy_root / "quran_uthmani_passages/quran_uthmani_passage_windows_v1.csv")
    monkeypatch.setattr(repo, "LEGACY_QURAN_TRANSLATION_PATH", fake_legacy_root / "quran_translations/quran_en_single_translation.csv")
    monkeypatch.setattr(repo, "LEGACY_QURAN_PASSAGE_NEIGHBOR_INDEX_PATH", fake_legacy_root / "quran_passage_neighbors/passage_neighbors_v1.jsonl")
    monkeypatch.setattr(repo, "LEGACY_ASSET_PATHS", {
        "quran_arabic": repo.LEGACY_QURAN_ARABIC_PATH,
        "quran_passage": repo.LEGACY_QURAN_PASSAGE_DATA_PATH,
        "quran_uthmani": repo.LEGACY_QURAN_UTHMANI_DATA_PATH,
        "quran_uthmani_passage": repo.LEGACY_QURAN_UTHMANI_PASSAGE_DATA_PATH,
        "quran_translation_en": repo.LEGACY_QURAN_TRANSLATION_PATH,
        "quran_passage_neighbors": repo.LEGACY_QURAN_PASSAGE_NEIGHBOR_INDEX_PATH,
    })

    bundle = repo.resolve_runtime_artifact_bundle(artifact_root=tmp_path / "does-not-exist", version="v9", require_bundle=False, prefer_bundle=True)
    assert bundle.source == "legacy_processed_fallback"
    assert bundle.manifest_path is None


def test_resolve_runtime_artifact_bundle_raises_when_bundle_required(tmp_path: Path) -> None:
    with pytest.raises(repo.RuntimeArtifactError):
        repo.resolve_runtime_artifact_bundle(artifact_root=tmp_path, version="v404", require_bundle=True, prefer_bundle=True)
