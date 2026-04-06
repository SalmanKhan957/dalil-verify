from __future__ import annotations

import importlib
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")


bootstrap = importlib.import_module("domains.quran.verifier.bootstrap")
repo_mod = importlib.import_module("domains.quran.repositories.runtime_assets_repository")


class _DummyRuntime:
    def __init__(self) -> None:
        self.rows = [{"surah_no": 1, "ayah_no": 1}]
        self.passage_rows = [{"window_size": 2}]


def test_refresh_runtime_state_uses_resolved_artifact_bundle(monkeypatch, tmp_path: Path) -> None:
    bundle = repo_mod.QuranRuntimeArtifactBundle(
        version="vtest",
        source="runtime_bundle",
        root_dir=tmp_path,
        manifest_path=tmp_path / "manifest.json",
        quran_arabic_path=tmp_path / "quran.csv",
        quran_passage_path=tmp_path / "passages.csv",
        quran_uthmani_path=tmp_path / "uthmani.csv",
        quran_uthmani_passage_path=tmp_path / "uthmani_passages.csv",
        quran_translation_path=tmp_path / "translation.csv",
        quran_passage_neighbor_index_path=tmp_path / "neighbors.jsonl",
        manifest={"artifact_family": "quran_runtime", "artifact_version": "vtest", "assets": {}},
    )
    seen: dict[str, str] = {}
    monkeypatch.setattr(bootstrap, "_run_startup_source_governance_checks", lambda: None)
    monkeypatch.setattr(bootstrap, "resolve_runtime_artifact_bundle", lambda: bundle)
    monkeypatch.setattr(bootstrap, "load_passage_neighbor_lookup", lambda path: {"simple": {}, "uthmani": {}})

    def _fake_load_runtime(label, quran_path, passage_path, *, required, passage_neighbor_lookup=None):
        seen[f"{label}_quran_path"] = str(quran_path)
        seen[f"{label}_passage_path"] = str(passage_path)
        return _DummyRuntime()

    monkeypatch.setattr(bootstrap, "load_runtime", _fake_load_runtime)
    monkeypatch.setattr(bootstrap, "load_english_translation_map", lambda path: ({(1, 1): {"text": "In the name"}}, {"loaded": True, "row_count": 1, "path": str(path)}))
    bootstrap.refresh_runtime_state()
    assert seen["simple_quran_path"].endswith("quran.csv")
    assert seen["uthmani_quran_path"].endswith("uthmani.csv")
    assert bootstrap.RUNTIME_ARTIFACT_INFO["source"] == "runtime_bundle"
    assert bootstrap.RUNTIME_ARTIFACT_INFO["version"] == "vtest"
