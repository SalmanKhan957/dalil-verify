from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.quran_runtime.matching import QuranShortlistIndex, QuranSurahSpanIndex


@dataclass
class CorpusRuntime:
    label: str
    quran_path: Path
    passage_path: Path
    rows: list[dict]
    passage_rows: list[dict]
    ayah_shortlist_index: QuranShortlistIndex | None
    passage_shortlist_index: QuranShortlistIndex | None
    surah_span_index: QuranSurahSpanIndex | None
    exact_light_groups: dict[str, list[dict]]
    exact_aggressive_groups: dict[str, list[dict]]
    exact_light_map: dict[str, dict | None]
    exact_aggressive_map: dict[str, dict | None]
    passage_exact_light_groups: dict[str, list[dict]]
    passage_exact_aggressive_groups: dict[str, list[dict]]
    passage_rows_by_window_size: dict[int, list[dict]]
    passage_row_lookup: dict[str, dict]
    passage_neighbor_lookup: dict[tuple[int, str], list[dict]]
