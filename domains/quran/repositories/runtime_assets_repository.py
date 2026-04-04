from __future__ import annotations

from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_QURAN_ARABIC_PATH = REPO_ROOT / "data/processed/quran/quran_arabic_canonical.csv"
DEFAULT_QURAN_PASSAGE_DATA_PATH = REPO_ROOT / "data/processed/quran_passages/quran_passage_windows_v1.csv"
DEFAULT_QURAN_UTHMANI_DATA_PATH = REPO_ROOT / "data/processed/quran_uthmani/quran_arabic_uthmani_canonical.csv"
DEFAULT_QURAN_UTHMANI_PASSAGE_DATA_PATH = REPO_ROOT / "data/processed/quran_uthmani_passages/quran_uthmani_passage_windows_v1.csv"
DEFAULT_QURAN_TRANSLATION_PATH = REPO_ROOT / "data/processed/quran_translations/quran_en_single_translation.csv"
DEFAULT_QURAN_PASSAGE_NEIGHBOR_INDEX_PATH = REPO_ROOT / "data/processed/quran_passage_neighbors/passage_neighbors_v1.jsonl"

RuntimeLabel = Literal["simple", "uthmani"]


def get_quran_path(*, label: RuntimeLabel = "simple") -> Path:
    return DEFAULT_QURAN_UTHMANI_DATA_PATH if label == "uthmani" else DEFAULT_QURAN_ARABIC_PATH


def get_passage_path(*, label: RuntimeLabel = "simple") -> Path:
    return DEFAULT_QURAN_UTHMANI_PASSAGE_DATA_PATH if label == "uthmani" else DEFAULT_QURAN_PASSAGE_DATA_PATH
