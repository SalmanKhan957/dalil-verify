from __future__ import annotations

import importlib
import json
from pathlib import Path

from pipelines.maintenance.rebuild_runtime_assets import rebuild_runtime_assets

repo = importlib.import_module("domains.quran.repositories.runtime_assets_repository")


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_rebuild_runtime_assets_copies_legacy_assets(monkeypatch, tmp_path: Path) -> None:
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

    bundle_dir = rebuild_runtime_assets(output_root=tmp_path / "runtime", version="v1-test")
    manifest_path = bundle_dir / "manifest.json"
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["artifact_family"] == "quran_runtime"
    assert payload["artifact_version"] == "v1-test"
    assert (bundle_dir / "quran/quran_arabic_canonical.csv").exists()
    assert (bundle_dir / "quran_passage_neighbors/passage_neighbors_v1.jsonl").exists()
