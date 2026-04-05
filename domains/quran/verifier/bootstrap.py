from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
import os
import time
import warnings

from fastapi import FastAPI

from domains.quran.repositories.runtime_assets_repository import (
    DEFAULT_QURAN_ARABIC_PATH,
    DEFAULT_QURAN_PASSAGE_DATA_PATH,
    DEFAULT_QURAN_PASSAGE_NEIGHBOR_INDEX_PATH,
    DEFAULT_QURAN_TRANSLATION_PATH,
    DEFAULT_QURAN_UTHMANI_DATA_PATH,
    DEFAULT_QURAN_UTHMANI_PASSAGE_DATA_PATH,
)
from domains.quran.repositories.context import inspect_quran_repository_runtime
from domains.quran.verifier.loaders import load_runtime
from domains.quran.verifier.matching import load_passage_neighbor_lookup
from domains.quran.verifier.translation import load_english_translation_map
from domains.quran.verifier.types import CorpusRuntime
from domains.source_registry.invariants import run_source_governance_checks

QURAN_DATA_PATH = DEFAULT_QURAN_ARABIC_PATH
QURAN_PASSAGE_DATA_PATH = DEFAULT_QURAN_PASSAGE_DATA_PATH
QURAN_UTHMANI_DATA_PATH = DEFAULT_QURAN_UTHMANI_DATA_PATH
QURAN_UTHMANI_PASSAGE_DATA_PATH = DEFAULT_QURAN_UTHMANI_PASSAGE_DATA_PATH
QURAN_EN_TRANSLATION_PATH = DEFAULT_QURAN_TRANSLATION_PATH
QURAN_PASSAGE_NEIGHBOR_INDEX_PATH = DEFAULT_QURAN_PASSAGE_NEIGHBOR_INDEX_PATH

SIMPLE_RUNTIME: CorpusRuntime | None = None
UTHMANI_RUNTIME: CorpusRuntime | None = None
ENGLISH_TRANSLATION_MAP: dict[tuple[int, int], dict] = {}
ENGLISH_TRANSLATION_INFO: dict = {"loaded": False, "row_count": 0, "path": str(QURAN_EN_TRANSLATION_PATH)}
PASSAGE_NEIGHBOR_LOOKUP: dict[str, dict[tuple[int, str], list[dict]]] = {"simple": {}, "uthmani": {}}
RUNTIME_BOOT_INFO: dict[str, object] = {
    "loaded": False,
    "load_count": 0,
    "last_loaded_at": None,
    "load_duration_ms": None,
}
SOURCE_GOVERNANCE_INFO: dict[str, object] = {
    "checked": False,
    "issue_count": 0,
    "warning_count": 0,
    "error_count": 0,
    "issues": [],
    "quran_repository": {},
}

_RUNTIME_LOCK = Lock()


def _run_startup_source_governance_checks() -> None:
    global SOURCE_GOVERNANCE_INFO

    strict = os.getenv("DALIL_STRICT_SOURCE_GOVERNANCE", "false").strip().lower() in {"1", "true", "yes", "on"}
    issues = run_source_governance_checks(strict=strict)
    quran_repository = inspect_quran_repository_runtime()
    SOURCE_GOVERNANCE_INFO = {
        "checked": True,
        "issue_count": len(issues) + int(quran_repository.get("issue_count", 0)),
        "warning_count": sum(1 for issue in issues if issue.severity == "warning") + int(
            quran_repository.get("warning_count", 0)
        ),
        "error_count": sum(1 for issue in issues if issue.severity == "error") + int(
            quran_repository.get("error_count", 0)
        ),
        "issues": [
            {
                "code": issue.code,
                "source_id": issue.source_id,
                "message": issue.message,
                "severity": issue.severity,
            }
            for issue in issues
        ]
        + list(quran_repository.get("issues", [])),
        "quran_repository": quran_repository,
    }

    for issue in issues:
        warnings.warn(f"[dalil-governance:{issue.severity}] {issue.message}")
    for issue in quran_repository.get("issues", []):
        warnings.warn(f"[dalil-governance:{issue['severity']}] {issue['message']}")

    if strict and int(quran_repository.get("error_count", 0)) > 0:
        joined = "; ".join(issue["message"] for issue in quran_repository.get("issues", []))
        raise RuntimeError(joined)


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    ensure_runtime_state_loaded()
    yield


def runtime_state_loaded() -> bool:
    return SIMPLE_RUNTIME is not None and bool(ENGLISH_TRANSLATION_INFO.get("loaded", False))


def ensure_runtime_state_loaded(*, force: bool = False) -> None:
    if runtime_state_loaded() and not force:
        return
    with _RUNTIME_LOCK:
        if runtime_state_loaded() and not force:
            return
        refresh_runtime_state()


def refresh_runtime_state() -> None:
    global SIMPLE_RUNTIME, UTHMANI_RUNTIME
    global ENGLISH_TRANSLATION_MAP, ENGLISH_TRANSLATION_INFO, PASSAGE_NEIGHBOR_LOOKUP
    global RUNTIME_BOOT_INFO

    started = time.perf_counter()
    _run_startup_source_governance_checks()
    PASSAGE_NEIGHBOR_LOOKUP = load_passage_neighbor_lookup(QURAN_PASSAGE_NEIGHBOR_INDEX_PATH)
    SIMPLE_RUNTIME = load_runtime(
        "simple",
        QURAN_DATA_PATH,
        QURAN_PASSAGE_DATA_PATH,
        required=True,
        passage_neighbor_lookup=PASSAGE_NEIGHBOR_LOOKUP.get("simple", {}),
    )
    UTHMANI_RUNTIME = load_runtime(
        "uthmani",
        QURAN_UTHMANI_DATA_PATH,
        QURAN_UTHMANI_PASSAGE_DATA_PATH,
        required=False,
        passage_neighbor_lookup=PASSAGE_NEIGHBOR_LOOKUP.get("uthmani", {}),
    )
    ENGLISH_TRANSLATION_MAP, ENGLISH_TRANSLATION_INFO = load_english_translation_map(QURAN_EN_TRANSLATION_PATH)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    RUNTIME_BOOT_INFO = {
        "loaded": True,
        "load_count": int(RUNTIME_BOOT_INFO.get("load_count", 0)) + 1,
        "last_loaded_at": time.time(),
        "load_duration_ms": duration_ms,
    }
