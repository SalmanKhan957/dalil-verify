from __future__ import annotations

from pathlib import Path

from domains.quran.verifier.matching import (
    QuranShortlistIndex,
    QuranSurahSpanIndex,
    build_exact_groups,
    build_passage_row_lookup,
    build_passage_rows_by_window_size,
    build_unique_exact_map,
)
from domains.quran.verifier.ranking import load_quran_dataset, load_quran_passage_dataset
from domains.quran.verifier.types import CorpusRuntime


def load_runtime(
    label: str,
    quran_path: Path,
    passage_path: Path,
    *,
    required: bool,
    passage_neighbor_lookup: dict[tuple[int, str], list[dict]] | None = None,
) -> CorpusRuntime | None:
    if not quran_path.exists() or not passage_path.exists():
        if required:
            missing = quran_path if not quran_path.exists() else passage_path
            raise RuntimeError(
                f"{label.title()} Quran dataset not found at: {missing}. "
                f"Ensure the corpus is generated before starting the API."
            )
        return None

    rows = load_quran_dataset(quran_path)
    passage_rows = load_quran_passage_dataset(passage_path)
    exact_light_groups = build_exact_groups(rows, "text_normalized_light")
    exact_aggressive_groups = build_exact_groups(rows, "text_normalized_aggressive")
    passage_exact_light_groups = build_exact_groups(passage_rows, "text_normalized_light")
    passage_exact_aggressive_groups = build_exact_groups(passage_rows, "text_normalized_aggressive")

    return CorpusRuntime(
        label=label,
        quran_path=quran_path,
        passage_path=passage_path,
        rows=rows,
        passage_rows=passage_rows,
        ayah_shortlist_index=QuranShortlistIndex(rows),
        passage_shortlist_index=QuranShortlistIndex(passage_rows),
        surah_span_index=QuranSurahSpanIndex(rows),
        exact_light_groups=exact_light_groups,
        exact_aggressive_groups=exact_aggressive_groups,
        exact_light_map=build_unique_exact_map(exact_light_groups),
        exact_aggressive_map=build_unique_exact_map(exact_aggressive_groups),
        passage_exact_light_groups=passage_exact_light_groups,
        passage_exact_aggressive_groups=passage_exact_aggressive_groups,
        passage_rows_by_window_size=build_passage_rows_by_window_size(passage_rows),
        passage_row_lookup=build_passage_row_lookup(passage_rows),
        passage_neighbor_lookup=passage_neighbor_lookup or {},
    )
