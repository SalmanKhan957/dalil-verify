from __future__ import annotations

import pytest

from domains.quran.repositories.context import inspect_quran_repository_runtime, resolve_quran_repository_context


def test_resolve_quran_repository_context_reads_env_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DALIL_QURAN_REPOSITORY_MODE", "db_preferred")
    monkeypatch.setenv("DALIL_DATABASE_URL", "sqlite:///tmp/dalil.db")

    context = resolve_quran_repository_context()

    assert context.repository_mode == "db_preferred"
    assert context.database_url == "sqlite:///tmp/dalil.db"
    assert context.quran_work_source_id == "quran:tanzil-simple"
    assert context.translation_work_source_id == "quran:towards-understanding-en"
    assert context.source_resolution_strategy in {"registry", "bootstrap_fallback"}


def test_resolve_quran_repository_context_reads_env_source_ids(monkeypatch) -> None:
    monkeypatch.setenv("DALIL_QURAN_TEXT_SOURCE_ID", "quran:tanzil-simple")
    monkeypatch.setenv("DALIL_QURAN_TRANSLATION_SOURCE_ID", "quran:towards-understanding-en")

    context = resolve_quran_repository_context()

    assert context.quran_work_source_id == "quran:tanzil-simple"
    assert context.translation_work_source_id == "quran:towards-understanding-en"


def test_resolve_quran_repository_context_raises_for_db_only_without_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DALIL_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError):
        resolve_quran_repository_context(repository_mode="db_only")


def test_context_raises_when_requested_translation_source_is_invalid() -> None:
    try:
        resolve_quran_repository_context(translation_work_source_id="hadith:sahih-bukhari-en")
    except ValueError as exc:
        assert "translation source" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected invalid translation source to raise ValueError")


def test_inspect_quran_repository_runtime_reports_invalid_translation(monkeypatch) -> None:
    monkeypatch.setenv("DALIL_QURAN_TRANSLATION_SOURCE_ID", "hadith:sahih-bukhari-en")
    report = inspect_quran_repository_runtime()
    assert report["checked"] is True
    assert report["error_count"] == 1
    assert report["issues"][0]["code"] == "quran_translation_source_not_available"
