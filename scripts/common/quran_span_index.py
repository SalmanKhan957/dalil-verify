from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from scripts.common.text_normalization import normalize_arabic_aggressive, normalize_arabic_light, tokenize
from scripts.evaluation.quran_verifier_baseline import compute_candidate_score


@dataclass
class _JoinedSurahIndex:
    surah_no: int
    rows: list[dict[str, Any]]
    joined_display: str
    joined_light: str
    joined_aggressive: str
    light_ranges: list[tuple[int, int]]
    aggressive_ranges: list[tuple[int, int]]


class QuranSurahSpanIndex:
    """
    Dynamic same-surah passage index for long contiguous Quran queries.

    Purpose:
    - support exact/contained matches longer than the precomputed 2-4 ayah windows
    - keep the verifier within a same-surah boundary only
    - return contiguous ayah spans with canonical citation boundaries
    """

    def __init__(self, ayah_rows: list[dict[str, Any]]) -> None:
        self.ayah_rows = ayah_rows
        self.surah_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
        self.surah_index: dict[int, _JoinedSurahIndex] = {}
        self._dynamic_row_cache: dict[tuple[int, int, int], dict[str, Any]] = {}
        self._build()

    def _build(self) -> None:
        for row in self.ayah_rows:
            self.surah_rows[int(row["surah_no"])].append(row)

        for surah_no, rows in self.surah_rows.items():
            rows.sort(key=lambda r: int(r["ayah_no"]))
            joined_display, _ = self._join_texts([r["text_display"] for r in rows])
            joined_light, light_ranges = self._join_texts([r["text_normalized_light"] for r in rows])
            joined_aggressive, aggressive_ranges = self._join_texts([r["text_normalized_aggressive"] for r in rows])
            self.surah_index[surah_no] = _JoinedSurahIndex(
                surah_no=surah_no,
                rows=rows,
                joined_display=joined_display,
                joined_light=joined_light,
                joined_aggressive=joined_aggressive,
                light_ranges=light_ranges,
                aggressive_ranges=aggressive_ranges,
            )

    @staticmethod
    def _join_texts(texts: list[str]) -> tuple[str, list[tuple[int, int]]]:
        parts: list[str] = []
        ranges: list[tuple[int, int]] = []
        cursor = 0
        for text in texts:
            clean = (text or "").strip()
            start = cursor
            parts.append(clean)
            cursor += len(clean)
            end = cursor
            ranges.append((start, end))
            cursor += 1
        return " ".join(parts).strip(), ranges

    def find_long_passage_candidates(
        self,
        query: str,
        *,
        ayah_seed_candidates: list[dict[str, Any]] | None = None,
        passage_seed_candidates: list[dict[str, Any]] | None = None,
        min_window_size: int = 5,
        max_window_size: int = 12,
        top_k: int = 5,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        exact_candidates = self._find_contained_span_candidates(
            query,
            min_window_size=min_window_size,
            top_k=top_k,
        )
        if exact_candidates:
            return exact_candidates[:top_k], {
                "engine": "surah_span_exact",
                "candidate_count": len(exact_candidates[:top_k]),
                "surah_count_scanned": len(self.surah_index),
            }

        expanded_candidates = self._expand_seed_surahs(
            query,
            ayah_seed_candidates=ayah_seed_candidates or [],
            passage_seed_candidates=passage_seed_candidates or [],
            min_window_size=min_window_size,
            max_window_size=max_window_size,
            top_k=top_k,
        )
        if expanded_candidates:
            seed_surahs = sorted({int(c["row"]["surah_no"]) for c in expanded_candidates})
            return expanded_candidates[:top_k], {
                "engine": "dynamic_expand",
                "candidate_count": len(expanded_candidates[:top_k]),
                "seed_surahs": seed_surahs,
                "max_window_size": max_window_size,
            }

        return [], {"engine": "none", "candidate_count": 0}

    def _find_contained_span_candidates(
        self,
        query: str,
        *,
        min_window_size: int,
        top_k: int,
    ) -> list[dict[str, Any]]:
        light_query = normalize_arabic_light(query)
        aggressive_query = normalize_arabic_aggressive(query)
        light_query_tokens = tokenize(light_query)
        aggressive_query_tokens = tokenize(aggressive_query)
        if not light_query:
            return []

        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()

        for surah_no, index in self.surah_index.items():
            for match_mode, joined_text, ranges, needle in (
                ("exact_light", index.joined_light, index.light_ranges, light_query),
                ("exact_aggressive", index.joined_aggressive, index.aggressive_ranges, aggressive_query),
            ):
                if not needle:
                    continue
                start = joined_text.find(needle)
                while start != -1:
                    end = start + len(needle)
                    ayah_start, ayah_end = self._map_span_to_ayahs(ranges, start, end)
                    if ayah_start is not None and ayah_end is not None:
                        window_size = ayah_end - ayah_start + 1
                        if window_size >= min_window_size:
                            row = self._get_dynamic_row(surah_no, ayah_start, ayah_end)
                            candidate = compute_candidate_score(
                                normalized_query=light_query,
                                query_tokens=light_query_tokens,
                                row=row,
                                original_query=query,
                                aggressive_query=aggressive_query,
                                aggressive_query_tokens=aggressive_query_tokens,
                            )
                            candidate["retrieval_engine"] = "surah_span_exact"
                            candidate["span_match_type"] = match_mode
                            key = row["canonical_source_id"]
                            if key not in seen:
                                seen.add(key)
                                candidates.append(candidate)
                    start = joined_text.find(needle, start + 1)

        candidates.sort(
            key=lambda x: (
                x["score"],
                x["exact_normalized_light"],
                x["contains_query_in_text_light"],
                x["token_coverage"],
            ),
            reverse=True,
        )
        return candidates[:top_k]

    def _expand_seed_surahs(
        self,
        query: str,
        *,
        ayah_seed_candidates: list[dict[str, Any]],
        passage_seed_candidates: list[dict[str, Any]],
        min_window_size: int,
        max_window_size: int,
        top_k: int,
    ) -> list[dict[str, Any]]:
        seed_surahs: list[int] = []
        for candidate in passage_seed_candidates[:5]:
            row = candidate.get("row") or {}
            surah_no = row.get("surah_no")
            if surah_no is None:
                continue
            surah_no = int(surah_no)
            if surah_no not in seed_surahs:
                seed_surahs.append(surah_no)
            if len(seed_surahs) >= 2:
                break

        for candidate in ayah_seed_candidates[:5]:
            row = candidate.get("row") or {}
            surah_no = row.get("surah_no")
            if surah_no is None:
                continue
            surah_no = int(surah_no)
            if surah_no not in seed_surahs:
                seed_surahs.append(surah_no)
            if len(seed_surahs) >= 2:
                break

        if not seed_surahs:
            return []

        normalized_query = normalize_arabic_light(query)
        aggressive_query = normalize_arabic_aggressive(query)
        query_tokens = tokenize(normalized_query)
        aggressive_query_tokens = tokenize(aggressive_query)
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()

        for surah_no in seed_surahs:
            rows = self.surah_rows.get(surah_no, [])
            ayah_count = len(rows)
            if ayah_count < min_window_size:
                continue

            max_len = min(max_window_size, ayah_count)
            for window_size in range(min_window_size, max_len + 1):
                for start_ayah in range(1, ayah_count - window_size + 2):
                    end_ayah = start_ayah + window_size - 1
                    row = self._get_dynamic_row(surah_no, start_ayah, end_ayah)
                    key = row["canonical_source_id"]
                    if key in seen:
                        continue
                    seen.add(key)
                    candidate = compute_candidate_score(
                        normalized_query=normalized_query,
                        query_tokens=query_tokens,
                        row=row,
                        original_query=query,
                        aggressive_query=aggressive_query,
                        aggressive_query_tokens=aggressive_query_tokens,
                    )
                    candidate["retrieval_engine"] = "dynamic_expand"
                    candidate["span_match_type"] = "seed_surah_expand"
                    candidates.append(candidate)

        candidates.sort(
            key=lambda x: (
                x["score"],
                x["exact_normalized_light"],
                x["contains_query_in_text_light"],
                x["token_coverage"],
            ),
            reverse=True,
        )
        return candidates[:top_k]

    @staticmethod
    def _map_span_to_ayahs(
        ranges: list[tuple[int, int]],
        span_start: int,
        span_end: int,
    ) -> tuple[int | None, int | None]:
        start_idx = None
        end_idx = None
        last_char = max(span_end - 1, span_start)
        for idx, (start, end) in enumerate(ranges):
            if start_idx is None and span_start < end:
                start_idx = idx + 1
            if start <= last_char < end:
                end_idx = idx + 1
                break
        return start_idx, end_idx

    def _get_dynamic_row(self, surah_no: int, start_ayah: int, end_ayah: int) -> dict[str, Any]:
        cache_key = (surah_no, start_ayah, end_ayah)
        cached = self._dynamic_row_cache.get(cache_key)
        if cached is not None:
            return cached

        rows = self.surah_rows[surah_no][start_ayah - 1 : end_ayah]
        first = rows[0]
        citation = f"Quran {surah_no}:{start_ayah}-{end_ayah}"
        component_citations = [f"Quran {surah_no}:{row['ayah_no']}" for row in rows]
        component_source_ids = [f"quran:{surah_no}:{row['ayah_no']}:ar" for row in rows]
        dynamic_row = {
            "source_type": "quran_passage",
            "source_id": f"QUR-AR-DYN-PASSAGE-{surah_no:03d}-{start_ayah:03d}-{end_ayah:03d}",
            "canonical_source_id": f"quran_passage:{surah_no}:{start_ayah}-{end_ayah}:ar",
            "citation_string": citation,
            "surah_no": surah_no,
            "start_ayah": start_ayah,
            "end_ayah": end_ayah,
            "window_size": end_ayah - start_ayah + 1,
            "surah_name_ar": first.get("surah_name_ar") or "",
            "translation_name": "",
            "text_display": " ".join((row.get("text_display") or "").strip() for row in rows).strip(),
            "text_normalized_light": " ".join((row.get("text_normalized_light") or "").strip() for row in rows).strip(),
            "text_normalized_aggressive": " ".join((row.get("text_normalized_aggressive") or "").strip() for row in rows).strip(),
            "component_citations_json": json.dumps(component_citations, ensure_ascii=False),
            "component_source_ids_json": json.dumps(component_source_ids, ensure_ascii=False),
        }
        dynamic_row["tokens_light"] = tokenize(dynamic_row["text_normalized_light"])
        dynamic_row["tokens_aggressive"] = tokenize(dynamic_row["text_normalized_aggressive"])
        self._dynamic_row_cache[cache_key] = dynamic_row
        return dynamic_row
