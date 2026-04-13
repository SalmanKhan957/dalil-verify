from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "Dalil Verify"
    env: str = "development"
    repo_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    quran_runtime_artifact_root: Path = Field(
        default_factory=lambda: Path(
            os.getenv(
                "DALIL_QURAN_RUNTIME_ARTIFACT_ROOT",
                str(Path(__file__).resolve().parents[2] / "data" / "runtime" / "quran"),
            )
        )
    )
    quran_runtime_artifact_version: str = Field(
        default_factory=lambda: os.getenv("DALIL_QURAN_RUNTIME_ARTIFACT_VERSION", "v1").strip() or "v1"
    )
    quran_runtime_require_bundle: bool = Field(
        default_factory=lambda: os.getenv("DALIL_QURAN_RUNTIME_REQUIRE_BUNDLE", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    anchor_store_backend: str = Field(
        default_factory=lambda: (os.getenv("DALIL_ANCHOR_STORE_BACKEND", "memory").strip().lower() or "memory")
    )
    anchor_store_sqlite_path: Path = Field(
        default_factory=lambda: Path(
            os.getenv(
                "DALIL_ANCHOR_STORE_SQLITE_PATH",
                str(Path(__file__).resolve().parents[2] / "data" / "runtime" / "conversation" / "anchor_store.sqlite3"),
            )
        )
    )
    public_topical_tafsir_enabled: bool = Field(
        default_factory=lambda: os.getenv("DALIL_PUBLIC_TOPICAL_TAFSIR_ENABLED", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    public_topical_hadith_enabled: bool = Field(
        default_factory=lambda: os.getenv("DALIL_PUBLIC_TOPICAL_HADITH_ENABLED", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    renderer_backend: str = Field(
        default_factory=lambda: (os.getenv("DALIL_RENDERER_BACKEND", "deterministic").strip().lower() or "deterministic")
    )
    renderer_model: str = Field(
        default_factory=lambda: os.getenv("DALIL_RENDERER_MODEL", "gpt-5.4-mini").strip() or "gpt-5.4-mini"
    )
    renderer_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("DALIL_RENDERER_TIMEOUT_SECONDS", "20").strip() or "20")
    )
    renderer_max_output_tokens: int = Field(
        default_factory=lambda: int(os.getenv("DALIL_RENDERER_MAX_OUTPUT_TOKENS", "800").strip() or "800")
    )
    renderer_followups_enabled: bool = Field(
        default_factory=lambda: os.getenv("DALIL_RENDERER_FOLLOWUPS_ENABLED", "true").strip().lower()
        not in {"0", "false", "no", "off"}
    )
    renderer_chat_style_enabled: bool = Field(
        default_factory=lambda: os.getenv("DALIL_RENDERER_CHAT_STYLE_ENABLED", "true").strip().lower()
        not in {"0", "false", "no", "off"}
    )
    renderer_verbosity_default: str = Field(
        default_factory=lambda: os.getenv("DALIL_RENDERER_VERBOSITY_DEFAULT", "standard").strip().lower() or "standard"
    )
    openai_api_key: str = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "").strip()
    )
    quran_runtime_prefer_bundle: bool = Field(
        default_factory=lambda: os.getenv("DALIL_QURAN_RUNTIME_PREFER_BUNDLE", "true").strip().lower()
        not in {"0", "false", "no", "off"}
    )


settings = Settings()
