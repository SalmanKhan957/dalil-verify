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
    quran_runtime_prefer_bundle: bool = Field(
        default_factory=lambda: os.getenv("DALIL_QURAN_RUNTIME_PREFER_BUNDLE", "true").strip().lower()
        not in {"0", "false", "no", "off"}
    )


settings = Settings()
