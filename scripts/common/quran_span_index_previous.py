
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from scripts.common.text_normalization import normalize_arabic_aggressive, normalize_arabic_light, tokenize
from scripts.evaluation.quran_verifier_baseline import compute_candidate_score


GIANT_ANCHOR_SIZE = 5
GIANT_MIN_TOKEN_COUNT = 60
GIANT_PARTIAL_MIN_COVERAGE = 0.55
GIANT_PARTIAL_MAX_SURAHS = 2
GIANT_PARTIAL_MAX_EXPANSION_AYAHS = 2
MEDIUM_PARTIAL_MAX_WINDOW_SIZE = 8
MEDIUM_PARTIAL_MIN_SCORE = 35.0
MEDIUM_PARTIAL_MIN_COVERAGE = 65.0


@dataclass
class _JoinedSurahIndex:
    surah_no: int
    rows: list[dict[str, Any]]
    joined_display: str
    joined_light: str
    joined_aggressive: str
    light_ranges: list[tuple[int, int]]
    aggressive_ranges: list[tuple[int, int]]
    light_tokens: list[str]
    light_token_ayahs: list[int]
    light_token_positions: dict[str, list[int]]
    aggressive_tokens: list[str]
    aggressive_token_ayahs: list[int]
    aggressive_token_positions: dict[str, list[int]]
    light_ngram_positions: dict[tuple[str, ...], list[int]]
    aggressive_ngram_positions: dict[tuple[str, ...], list[int]]


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
        self._exact_span_light_map: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
        self._exact_span_aggressive_map: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
        self._build()

    def _build(self) -> None:
        for row in self.ayah_rows:
            self.surah_rows[int(row["surah_no"])].append(row)

        for surah_no, rows in self.surah_rows.items():
            rows.sort(key=lambda r: int(r["ayah_no"]))
            joined_display, _ = self._join_texts([r["text_display"] for r in rows])
            joined_light, light_ranges = self._join_texts([r["text_normalized_light"] for r in rows])
            joined_aggressive, aggressive_ranges = self._join_texts([r["text_normalized_aggressive"] for r in rows])
            light_tokens, light_token_ayahs, light_token_positions = self._flatten_token_stream(rows, "tokens_light")
            aggressive_tokens, aggressive_token_ayahs, aggressive_token_positions = self._flatten_token_stream(rows, "tokens_aggressive")
            light_ngram_positions = self._build_ngram_position_map(light_tokens, n=GIANT_ANCHOR_SIZE)
            aggressive_ngram_positions = self._build_ngram_position_map(aggressive_tokens, n=GIANT_ANCHOR_SIZE)
            self._index_exact_spans(surah_no, rows, min_window_size=2, max_window_size=40)
            self.surah_index[surah_no] = _JoinedSurahIndex(
                surah_no=surah_no,
                rows=rows,
                joined_display=joined_display,
                joined_light=joined_light,
                joined_aggressive=joined_aggressive,
                light_ranges=light_ranges,
                aggressive_ranges=aggressive_ranges,
                light_tokens=light_tokens,
                light_token_ayahs=light_token_ayahs,
                light_token_positions=light_token_positions,
                aggressive_tokens=aggressive_tokens,
                aggressive_token_ayahs=aggressive_token_ayahs,
                aggressive_token_positions=aggressive_token_positions,
                light_ngram_positions=light_ngram_positions,
                aggressive_ngram_positions=aggressive_ngram_positions,
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

    @staticmethod
    def _flatten_token_stream(
        rows: list[dict[str, Any]],
        token_field: str,
    ) -> tuple[list[str], list[int], dict[str, list[int]]]:
        tokens: list[str] = []
        token_ayahs: list[int] = []
        positions: dict[str, list[int]] = defaultdict(list)
        for row in rows:
            ayah_no = int(row["ayah_no"])
            for token in row.get(token_field) or []:
                idx = len(tokens)
                tokens.append(token)
                token_ayahs.append(ayah_no)
                positions[token].append(idx)
        return tokens, token_ayahs, dict(positions)

    @staticmethod
    def _build_ngram_position_map(
        tokens: list[str],
        *,
        n: int,
    ) -> dict[tuple[str, ...], list[int]]:
        positions: dict[tuple[str, ...], list[int]] = defaultdict(list)
        if n <= 0 or len(tokens) < n:
            return {}
        for idx in range(len(tokens) - n + 1):
            positions[tuple(tokens[idx : idx + n])].append(idx)
        return dict(positions)

    def _index_exact_spans(self, surah_no: int, rows: list[dict[str, Any]], *, min_window_size: int, max_window_size: int) -> None:
        total = len(rows)
        for start_idx in range(total):
            light_parts: list[str] = []
            aggressive_parts: list[str] = []
            for end_idx in range(start_idx, min(total, start_idx + max_window_size)):
                light_parts.append((rows[end_idx].get("text_normalized_light") or "").strip())
                aggressive_parts.append((rows[end_idx].get("text_normalized_aggressive") or "").strip())
                window_size = end_idx - start_idx + 1
                if window_size < min_window_size:
                    continue
                start_ayah = int(rows[start_idx]["ayah_no"])
                end_ayah = int(rows[end_idx]["ayah_no"])
                key = (surah_no, start_ayah, end_ayah)
                light_text = " ".join(light_parts).strip()
                aggressive_text = " ".join(aggressive_parts).strip()
                if light_text:
                    self._exact_span_light_map[light_text].append(key)
                if aggressive_text:
                    self._exact_span_aggressive_map[aggressive_text].append(key)

    def find_exact_span_lookup_candidates(
        self,
        query: str,
        *,
        min_window_size: int = 4,
        top_k: int = 5,
        surah_scope: list[int] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        light_query = normalize_arabic_light(query)
        aggressive_query = normalize_arabic_aggressive(query)
        light_query_tokens = tokenize(light_query)
        aggressive_query_tokens = tokenize(aggressive_query)
        scope = set(int(s) for s in surah_scope) if surah_scope else None

        candidate_keys: list[tuple[int, int, int, str]] = []
        seen_keys: set[tuple[int, int, int]] = set()
        for match_mode, exact_map, needle in (
            ("exact_light_cache", self._exact_span_light_map, light_query),
            ("exact_aggressive_cache", self._exact_span_aggressive_map, aggressive_query),
        ):
            if not needle:
                continue
            for surah_no, start_ayah, end_ayah in exact_map.get(needle, []):
                if scope is not None and surah_no not in scope:
                    continue
                key3 = (surah_no, start_ayah, end_ayah)
                if key3 in seen_keys:
                    continue
                if end_ayah - start_ayah + 1 < min_window_size:
                    continue
                seen_keys.add(key3)
                candidate_keys.append((surah_no, start_ayah, end_ayah, match_mode))

        if not candidate_keys:
            return [], {"engine": "none", "candidate_count": 0}

        candidates: list[dict[str, Any]] = []
        for surah_no, start_ayah, end_ayah, match_mode in candidate_keys:
            row = self._get_dynamic_row(surah_no, start_ayah, end_ayah)
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
            candidates.append(candidate)

        ranked = self._rank_candidates(candidates, top_k=top_k)
        return ranked, {
            "engine": "surah_span_exact",
            "candidate_count": len(ranked),
            "surah_count_scanned": len({int(c["row"]["surah_no"]) for c in ranked}),
            "surah_scope": sorted({int(c["row"]["surah_no"]) for c in ranked}),
            "lookup_source": "precomputed_exact_span_map",
        }

    def find_medium_partial_passage_candidates(
        self,
        query: str,
        *,
        ayah_seed_candidates: list[dict[str, Any]] | None = None,
        passage_seed_candidates: list[dict[str, Any]] | None = None,
        likely_surahs: list[int] | None = None,
        min_window_size: int = 2,
        max_window_size: int = MEDIUM_PARTIAL_MAX_WINDOW_SIZE,
        top_k: int = 5,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        seed_ranges = self._collect_seed_ranges(
            ayah_seed_candidates=ayah_seed_candidates or [],
            passage_seed_candidates=passage_seed_candidates or [],
        )
        seed_surahs = sorted({surah_no for surah_no, _, _ in seed_ranges})
        surah_scope = sorted({*([int(s) for s in (likely_surahs or [])] or []), *seed_surahs})
        if not surah_scope and not seed_ranges:
            return [], {"engine": "none", "candidate_count": 0, "reason": "no_seed_scope"}

        candidate_pool: list[dict[str, Any]] = []
        lookup_source = "none"
        contained = self._find_contained_span_candidates(
            query,
            min_window_size=1,
            top_k=max(top_k * 4, 12),
            surah_scope=surah_scope or None,
        )
        if contained:
            lookup_source = "contained_partial_span"
            contained_seed_ranges: list[tuple[int, int, int]] = []
            for candidate in contained:
                row = candidate.get("row") or {}
                surah_no = int(row.get("surah_no") or 0)
                start_ayah = int(row.get("start_ayah") or row.get("ayah_no") or 0)
                end_ayah = int(row.get("end_ayah") or row.get("ayah_no") or 0)
                if surah_no and start_ayah and end_ayah:
                    contained_seed_ranges.append((surah_no, start_ayah, end_ayah))
                if int(row.get("window_size") or 1) >= min_window_size:
                    promoted = dict(candidate)
                    promoted["retrieval_engine"] = "surah_span_partial"
                    promoted["span_match_type"] = promoted.get("span_match_type") or "contained_partial"
                    candidate_pool.append(promoted)

            if contained_seed_ranges:
                expanded_from_contained = self._expand_around_seed_ranges(
                    query,
                    seed_ranges=contained_seed_ranges,
                    min_window_size=min_window_size,
                    max_window_size=max_window_size,
                    top_k=max(top_k * 4, 12),
                )
                for candidate in expanded_from_contained:
                    candidate["retrieval_engine"] = "surah_span_partial"
                    candidate["span_match_type"] = "contained_partial_expand"
                candidate_pool.extend(expanded_from_contained)

        if not candidate_pool and seed_ranges:
            lookup_source = "bounded_seed_expand"
            bounded_seed_candidates = self._expand_around_seed_ranges(
                query,
                seed_ranges=seed_ranges,
                min_window_size=min_window_size,
                max_window_size=max_window_size,
                top_k=max(top_k * 4, 12),
            )
            for candidate in bounded_seed_candidates:
                candidate["retrieval_engine"] = "surah_span_partial"
                candidate["span_match_type"] = "bounded_seed_partial"
            candidate_pool.extend(bounded_seed_candidates)

        filtered: list[dict[str, Any]] = []
        seen: set[str] = set()
        for candidate in candidate_pool:
            row = candidate.get("row") or {}
            if int(row.get("window_size") or 1) < min_window_size:
                continue
            score = float(candidate.get("score") or 0.0)
            coverage = float(candidate.get("token_coverage") or 0.0)
            contains_light = float(candidate.get("contains_query_in_text_light") or 0.0)
            if score < MEDIUM_PARTIAL_MIN_SCORE and coverage < MEDIUM_PARTIAL_MIN_COVERAGE and contains_light < 100.0:
                continue
            key = row.get("canonical_source_id")
            if not key or key in seen:
                continue
            seen.add(key)
            filtered.append(candidate)

        ranked = self._rank_candidates(filtered, top_k=top_k)
        if not ranked:
            return [], {
                "engine": "none",
                "candidate_count": 0,
                "reason": "no_medium_partial_match",
                "surah_scope": surah_scope,
                "seed_surahs": seed_surahs,
                "lookup_source": lookup_source,
                "max_window_size": max_window_size,
            }

        return ranked, {
            "engine": "surah_span_partial",
            "candidate_count": len(ranked),
            "surah_scope": sorted({int(c["row"]["surah_no"]) for c in ranked}),
            "seed_surahs": seed_surahs,
            "lookup_source": lookup_source,
            "max_window_size": max_window_size,
        }


    def find_giant_exact_passage_candidates(
        self,
        query: str,
        *,
        likely_surahs: list[int] | None = None,
        min_window_size: int = 4,
        top_k: int = 1,
        anchor_size: int = GIANT_ANCHOR_SIZE,
        min_token_count: int = GIANT_MIN_TOKEN_COUNT,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        light_query = normalize_arabic_light(query)
        aggressive_query = normalize_arabic_aggressive(query)
        light_query_tokens = tokenize(light_query)
        aggressive_query_tokens = tokenize(aggressive_query)
        if len(light_query_tokens) < max(min_token_count, anchor_size * 2):
            return [], {
                "engine": "none",
                "candidate_count": 0,
                "reason": "query_below_giant_threshold",
                "query_token_count": len(light_query_tokens),
                "anchor_size": anchor_size,
            }

        requested_scope = [int(s) for s in (likely_surahs or []) if int(s) in self.surah_index]
        scope_order = requested_scope or sorted(self.surah_index)

        candidates = self._find_giant_exact_candidates_for_mode(
            query=query,
            light_query=light_query,
            aggressive_query=aggressive_query,
            light_query_tokens=light_query_tokens,
            aggressive_query_tokens=aggressive_query_tokens,
            scope_order=scope_order,
            anchor_size=anchor_size,
            min_window_size=min_window_size,
            top_k=top_k,
        )
        if candidates:
            return candidates[:top_k], {
                "engine": "giant_exact_anchor",
                "candidate_count": len(candidates[:top_k]),
                "surah_scope": sorted({int(c["row"]["surah_no"]) for c in candidates[:top_k]}),
                "lookup_source": "anchor_ngram_exact",
                "anchor_size": anchor_size,
                "query_token_count": len(light_query_tokens),
            }

        if requested_scope:
            fallback_scope = [surah_no for surah_no in sorted(self.surah_index) if surah_no not in requested_scope]
            fallback_candidates = self._find_giant_exact_candidates_for_mode(
                query=query,
                light_query=light_query,
                aggressive_query=aggressive_query,
                light_query_tokens=light_query_tokens,
                aggressive_query_tokens=aggressive_query_tokens,
                scope_order=fallback_scope,
                anchor_size=anchor_size,
                min_window_size=min_window_size,
                top_k=top_k,
            )
            if fallback_candidates:
                return fallback_candidates[:top_k], {
                    "engine": "giant_exact_anchor",
                    "candidate_count": len(fallback_candidates[:top_k]),
                    "surah_scope": sorted({int(c["row"]["surah_no"]) for c in fallback_candidates[:top_k]}),
                    "lookup_source": "anchor_ngram_exact_fallback_all_surahs",
                    "anchor_size": anchor_size,
                    "query_token_count": len(light_query_tokens),
                }

        return [], {
            "engine": "none",
            "candidate_count": 0,
            "reason": "no_exact_anchor_match",
            "surah_scope": requested_scope or sorted(self.surah_index),
            "anchor_size": anchor_size,
            "query_token_count": len(light_query_tokens),
        }

    def find_long_passage_candidates(
        self,
        query: str,
        *,
        ayah_seed_candidates: list[dict[str, Any]] | None = None,
        passage_seed_candidates: list[dict[str, Any]] | None = None,
        likely_surahs: list[int] | None = None,
        min_window_size: int = 4,
        max_window_size: int = 12,
        top_k: int = 5,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        seed_ranges = self._collect_seed_ranges(
            ayah_seed_candidates=ayah_seed_candidates or [],
            passage_seed_candidates=passage_seed_candidates or [],
        )
        seed_surahs = sorted({surah_no for surah_no, _, _ in seed_ranges})
        surah_scope = sorted({*([int(s) for s in (likely_surahs or [])] or []), *seed_surahs})

        exact_candidates, exact_meta = self.find_exact_span_lookup_candidates(
            query,
            min_window_size=min_window_size,
            top_k=top_k,
            surah_scope=surah_scope or None,
        )
        if exact_candidates:
            return exact_candidates[:top_k], exact_meta

        exact_candidates = self._find_contained_span_candidates(
            query,
            min_window_size=min_window_size,
            top_k=top_k,
            surah_scope=surah_scope or None,
        )
        if exact_candidates:
            return exact_candidates[:top_k], {
                "engine": "surah_span_exact",
                "candidate_count": len(exact_candidates[:top_k]),
                "surah_count_scanned": len(surah_scope) if surah_scope else len(self.surah_index),
                "surah_scope": surah_scope,
                "lookup_source": "surah_scan_contains",
            }

        if not seed_ranges:
            return [], {"engine": "none", "candidate_count": 0}

        token_candidates = self._find_token_subsequence_seed_candidates(
            query,
            seed_ranges=seed_ranges,
            min_window_size=min_window_size,
            top_k=top_k,
        )
        if token_candidates:
            return token_candidates[:top_k], {
                "engine": "token_subsequence",
                "candidate_count": len(token_candidates[:top_k]),
                "seed_surahs": sorted({int(c["row"]["surah_no"]) for c in token_candidates}),
            }

        expanded_candidates = self._expand_around_seed_ranges(
            query,
            seed_ranges=seed_ranges,
            min_window_size=min_window_size,
            max_window_size=max_window_size,
            top_k=top_k,
        )
        if expanded_candidates:
            return expanded_candidates[:top_k], {
                "engine": "local_seed_expand",
                "candidate_count": len(expanded_candidates[:top_k]),
                "seed_surahs": sorted({int(c["row"]["surah_no"]) for c in expanded_candidates}),
                "max_window_size": max_window_size,
            }

        return [], {"engine": "none", "candidate_count": 0}

    def _find_contained_span_candidates(
        self,
        query: str,
        *,
        min_window_size: int,
        top_k: int,
        surah_scope: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        light_query = normalize_arabic_light(query)
        aggressive_query = normalize_arabic_aggressive(query)
        light_query_tokens = tokenize(light_query)
        aggressive_query_tokens = tokenize(aggressive_query)
        if not light_query:
            return []

        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()

        iterable = ((s, self.surah_index[s]) for s in surah_scope if s in self.surah_index) if surah_scope else self.surah_index.items()
        for surah_no, index in iterable:
            for match_mode, joined_text, ranges, needle in (
                ("exact_light", index.joined_light, index.light_ranges, light_query),
                ("exact_aggressive", index.joined_aggressive, index.aggressive_ranges, aggressive_query),
            ):
                if not needle:
                    continue
                start = joined_text.find(needle)
                while start != -1:
                    end = start + len(needle)
                    ayah_start, ayah_end = self._map_char_span_to_ayahs(ranges, start, end)
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

        return self._rank_candidates(candidates, top_k=top_k)



    @staticmethod
    def _build_exact_match_candidate(
        *,
        query: str,
        light_query: str,
        aggressive_query: str,
        row: dict[str, Any],
        retrieval_engine: str,
        span_match_type: str,
        anchor_size: int | None = None,
        anchor_start_token_idx: int | None = None,
    ) -> dict[str, Any]:
        exact_display = 100.0 if query.strip() == (row.get("text_display") or "").strip() else 0.0
        exact_normalized_light = 100.0 if light_query == (row.get("text_normalized_light") or "") else 0.0
        exact_normalized_aggressive = 100.0 if aggressive_query == (row.get("text_normalized_aggressive") or "") else 0.0
        token_overlap_count_light = len(row.get("tokens_light") or [])
        token_overlap_count_aggressive = len(row.get("tokens_aggressive") or [])
        candidate = {
            "score": 100.0,
            "exact_display": exact_display,
            "exact_normalized_light": exact_normalized_light,
            "exact_normalized_aggressive": exact_normalized_aggressive,
            "contains_query_in_text_light": 100.0,
            "contains_query_in_text_aggressive": 100.0 if aggressive_query else 0.0,
            "contains_text_in_query_light": 100.0,
            "ratio_score": 100.0,
            "token_set_score": 100.0,
            "aggressive_token_set_score": 100.0,
            "token_sort_score": 100.0,
            "partial_raw": 100.0,
            "adjusted_partial": 100.0,
            "token_overlap_count_light": token_overlap_count_light,
            "token_overlap_count_aggressive": token_overlap_count_aggressive,
            "token_coverage_light": 100.0,
            "token_coverage_aggressive": 100.0,
            "token_coverage": 100.0,
            "length_ratio": 1.0,
            "short_candidate_penalty": 0.0,
            "row": row,
            "retrieval_engine": retrieval_engine,
            "span_match_type": span_match_type,
        }
        if anchor_size is not None:
            candidate["anchor_size"] = anchor_size
        if anchor_start_token_idx is not None:
            candidate["anchor_start_token_idx"] = anchor_start_token_idx
        return candidate

    def find_giant_partial_passage_candidates(
        self,
        query: str,
        *,
        likely_surahs: list[int] | None = None,
        min_window_size: int = 2,
        top_k: int = 5,
        anchor_size: int = GIANT_ANCHOR_SIZE,
        min_token_count: int = GIANT_MIN_TOKEN_COUNT,
        min_coverage: float = GIANT_PARTIAL_MIN_COVERAGE,
        max_surahs: int = GIANT_PARTIAL_MAX_SURAHS,
        max_expansion_ayahs: int = GIANT_PARTIAL_MAX_EXPANSION_AYAHS,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        light_query = normalize_arabic_light(query)
        aggressive_query = normalize_arabic_aggressive(query)
        light_query_tokens = tokenize(light_query)
        aggressive_query_tokens = tokenize(aggressive_query)
        if len(light_query_tokens) < max(min_token_count, anchor_size * 2):
            return [], {
                "engine": "none",
                "candidate_count": 0,
                "reason": "query_below_giant_threshold",
                "query_token_count": len(light_query_tokens),
                "anchor_size": anchor_size,
            }

        requested_scope = [int(s) for s in (likely_surahs or []) if int(s) in self.surah_index]
        inferred_scope = requested_scope or self._infer_giant_surah_scope(
            light_query_tokens=light_query_tokens,
            aggressive_query_tokens=aggressive_query_tokens,
            anchor_size=anchor_size,
            max_surahs=max_surahs,
        )
        scope_order = inferred_scope[:max_surahs]
        if not scope_order:
            return [], {
                "engine": "giant_partial_anchor",
                "candidate_count": 0,
                "reason": "no_anchor_surah_scope",
                "query_token_count": len(light_query_tokens),
                "anchor_size": anchor_size,
            }

        anchor_candidates = self._find_giant_anchor_span_candidates_for_scope(
            query=query,
            light_query=light_query,
            aggressive_query=aggressive_query,
            light_query_tokens=light_query_tokens,
            aggressive_query_tokens=aggressive_query_tokens,
            scope_order=scope_order,
            min_window_size=min_window_size,
            max_expansion_ayahs=max_expansion_ayahs,
            top_k=top_k,
            anchor_size=anchor_size,
        )
        subsequence_candidates = self._find_giant_partial_candidates_for_scope(
            query=query,
            light_query=light_query,
            aggressive_query=aggressive_query,
            light_query_tokens=light_query_tokens,
            aggressive_query_tokens=aggressive_query_tokens,
            scope_order=scope_order,
            min_window_size=min_window_size,
            min_coverage=min_coverage,
            max_expansion_ayahs=max_expansion_ayahs,
            top_k=top_k,
        )
        candidates = self._rank_candidates(anchor_candidates + subsequence_candidates, top_k=top_k)
        return candidates[:top_k], {
            "engine": "giant_partial_anchor",
            "candidate_count": len(candidates[:top_k]),
            "surah_scope": scope_order,
            "lookup_source": "anchor_surah_token_subsequence",
            "anchor_size": anchor_size,
            "query_token_count": len(light_query_tokens),
            "min_coverage": round(min_coverage * 100, 2),
            "reason": "ok" if candidates else "giant_partial_no_match",
        }

    def _infer_giant_surah_scope(
        self,
        *,
        light_query_tokens: list[str],
        aggressive_query_tokens: list[str],
        anchor_size: int,
        max_surahs: int,
    ) -> list[int]:
        def sample_anchors(tokens: list[str]) -> list[tuple[str, ...]]:
            if len(tokens) < anchor_size:
                return []
            offsets = [0]
            mid = max((len(tokens) // 2) - (anchor_size // 2), 0)
            tail = max(len(tokens) - anchor_size, 0)
            quarter = max((len(tokens) // 4) - (anchor_size // 2), 0)
            three_quarter = max(((3 * len(tokens)) // 4) - (anchor_size // 2), 0)
            for off in (quarter, mid, three_quarter, tail):
                if off not in offsets:
                    offsets.append(off)
            anchors: list[tuple[str, ...]] = []
            for off in offsets:
                anchor = tuple(tokens[off : off + anchor_size])
                if len(anchor) == anchor_size and anchor not in anchors:
                    anchors.append(anchor)
            return anchors

        light_anchors = sample_anchors(light_query_tokens)
        aggressive_anchors = sample_anchors(aggressive_query_tokens)
        if not light_anchors and not aggressive_anchors:
            return []

        surah_scores: dict[int, float] = defaultdict(float)
        for surah_no, index in self.surah_index.items():
            for anchor in light_anchors:
                positions = index.light_ngram_positions.get(anchor, [])
                if positions:
                    surah_scores[surah_no] += 3.0 + min(len(positions), 4) * 0.25
            for anchor in aggressive_anchors:
                positions = index.aggressive_ngram_positions.get(anchor, [])
                if positions:
                    surah_scores[surah_no] += 2.0 + min(len(positions), 4) * 0.2

        ordered = sorted(surah_scores.items(), key=lambda item: item[1], reverse=True)
        if ordered:
            return [surah_no for surah_no, _ in ordered[:max_surahs]]

        rare_token_scores: dict[int, float] = defaultdict(float)

        def vote_with_rare_tokens(query_tokens: list[str], *, aggressive: bool) -> None:
            token_candidates = [token for token in set(query_tokens) if len(token) >= 3]
            token_rarity: list[tuple[int, str]] = []
            for token in token_candidates:
                surah_hits = 0
                for index in self.surah_index.values():
                    positions = (index.aggressive_token_positions if aggressive else index.light_token_positions).get(token)
                    if positions:
                        surah_hits += 1
                if surah_hits:
                    token_rarity.append((surah_hits, token))
            token_rarity.sort(key=lambda item: (item[0], -len(item[1]), item[1]))
            for surah_hits, token in token_rarity[:12]:
                for surah_no, index in self.surah_index.items():
                    positions = (index.aggressive_token_positions if aggressive else index.light_token_positions).get(token, [])
                    if positions:
                        boost = (2.0 if not aggressive else 1.5) / max(surah_hits, 1)
                        rare_token_scores[surah_no] += boost + min(len(positions), 4) * 0.05

        vote_with_rare_tokens(light_query_tokens, aggressive=False)
        vote_with_rare_tokens(aggressive_query_tokens, aggressive=True)
        fallback_ordered = sorted(rare_token_scores.items(), key=lambda item: item[1], reverse=True)
        return [surah_no for surah_no, _ in fallback_ordered[:max_surahs]]

    def _find_giant_anchor_span_candidates_for_scope(
        self,
        *,
        query: str,
        light_query: str,
        aggressive_query: str,
        light_query_tokens: list[str],
        aggressive_query_tokens: list[str],
        scope_order: list[int],
        min_window_size: int,
        max_expansion_ayahs: int,
        top_k: int,
        anchor_size: int,
    ) -> list[dict[str, Any]]:
        def sample_anchor_specs(tokens: list[str]) -> list[tuple[int, tuple[str, ...]]]:
            if len(tokens) < anchor_size:
                return []
            offsets = [0]
            quarter = max((len(tokens) // 4) - (anchor_size // 2), 0)
            mid = max((len(tokens) // 2) - (anchor_size // 2), 0)
            three_quarter = max(((3 * len(tokens)) // 4) - (anchor_size // 2), 0)
            tail = max(len(tokens) - anchor_size, 0)
            for off in (quarter, mid, three_quarter, tail):
                if off not in offsets:
                    offsets.append(off)
            specs: list[tuple[int, tuple[str, ...]]] = []
            for off in offsets:
                anchor = tuple(tokens[off : off + anchor_size])
                if len(anchor) == anchor_size and all(anchor != existing for _, existing in specs):
                    specs.append((off, anchor))
            return specs

        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        mode_specs = (
            (
                "giant_partial_anchor_span_light",
                light_query_tokens,
                "light_token_ayahs",
                "light_ngram_positions",
            ),
            (
                "giant_partial_anchor_span_aggressive",
                aggressive_query_tokens,
                "aggressive_token_ayahs",
                "aggressive_ngram_positions",
            ),
        )

        for surah_no in scope_order:
            index = self.surah_index.get(surah_no)
            if index is None:
                continue
            ayah_count = len(index.rows)

            for match_mode, query_tokens, ayahs_attr, ngram_attr in mode_specs:
                anchor_specs = sample_anchor_specs(query_tokens)
                if len(anchor_specs) < 2:
                    continue
                token_ayahs = getattr(index, ayahs_attr)
                ngram_positions: dict[tuple[str, ...], list[int]] = getattr(index, ngram_attr)

                matched: list[tuple[int, int]] = []
                last_pos = -1
                for q_offset, anchor in anchor_specs:
                    positions = ngram_positions.get(anchor, [])
                    chosen = next((pos for pos in positions if pos > last_pos), None)
                    if chosen is None:
                        continue
                    matched.append((q_offset, chosen))
                    last_pos = chosen

                if len(matched) < 2:
                    continue

                anchor_match_ratio = len(matched) / len(anchor_specs)
                if anchor_match_ratio < 0.6:
                    continue

                start_token_idx = matched[0][1]
                end_token_idx = matched[-1][1] + anchor_size
                if end_token_idx > len(token_ayahs):
                    continue

                ayah_start = token_ayahs[start_token_idx]
                ayah_end = token_ayahs[end_token_idx - 1]
                if ayah_start is None or ayah_end is None:
                    continue

                for expansion in range(0, max_expansion_ayahs + 1):
                    start_ayah = max(1, int(ayah_start) - expansion)
                    end_ayah = min(ayah_count, int(ayah_end) + expansion)
                    if end_ayah - start_ayah + 1 < min_window_size:
                        continue
                    row = self._get_dynamic_row(surah_no, start_ayah, end_ayah)
                    key = row["canonical_source_id"]
                    if key in seen:
                        continue
                    candidate = compute_candidate_score(
                        normalized_query=light_query,
                        query_tokens=light_query_tokens,
                        row=row,
                        original_query=query,
                        aggressive_query=aggressive_query,
                        aggressive_query_tokens=aggressive_query_tokens,
                    )
                    candidate["retrieval_engine"] = "giant_partial_anchor"
                    candidate["span_match_type"] = match_mode
                    candidate["anchor_match_ratio"] = round(anchor_match_ratio * 100, 2)
                    candidate["giant_partial_expansion_ayahs"] = expansion
                    seen.add(key)
                    candidates.append(candidate)

        return self._rank_candidates(candidates, top_k=top_k)

    def _find_giant_partial_candidates_for_scope(
        self,
        *,
        query: str,
        light_query: str,
        aggressive_query: str,
        light_query_tokens: list[str],
        aggressive_query_tokens: list[str],
        scope_order: list[int],
        min_window_size: int,
        min_coverage: float,
        max_expansion_ayahs: int,
        top_k: int,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()

        mode_specs = (
            (
                "giant_partial_subsequence_light",
                light_query_tokens,
                "light_tokens",
                "light_token_ayahs",
                "light_token_positions",
            ),
            (
                "giant_partial_subsequence_aggressive",
                aggressive_query_tokens,
                "aggressive_tokens",
                "aggressive_token_ayahs",
                "aggressive_token_positions",
            ),
        )

        for surah_no in scope_order:
            index = self.surah_index.get(surah_no)
            if index is None:
                continue

            ayah_count = len(index.rows)
            for match_mode, query_tokens, tokens_attr, ayahs_attr, positions_attr in mode_specs:
                if len(query_tokens) < 8:
                    continue
                best = self._best_token_subsequence_span(
                    query_tokens=query_tokens,
                    surah_tokens=getattr(index, tokens_attr),
                    surah_token_ayahs=getattr(index, ayahs_attr),
                    token_positions=getattr(index, positions_attr),
                )
                if not best:
                    continue

                coverage = float(best.get("coverage") or 0.0)
                ayah_start = best.get("ayah_start")
                ayah_end = best.get("ayah_end")
                if coverage < min_coverage or ayah_start is None or ayah_end is None:
                    continue

                for expansion in range(0, max_expansion_ayahs + 1):
                    start_ayah = max(1, int(ayah_start) - expansion)
                    end_ayah = min(ayah_count, int(ayah_end) + expansion)
                    if end_ayah - start_ayah + 1 < min_window_size:
                        continue
                    row = self._get_dynamic_row(surah_no, start_ayah, end_ayah)
                    key = row["canonical_source_id"]
                    if key in seen:
                        continue
                    candidate = compute_candidate_score(
                        normalized_query=light_query,
                        query_tokens=light_query_tokens,
                        row=row,
                        original_query=query,
                        aggressive_query=aggressive_query,
                        aggressive_query_tokens=aggressive_query_tokens,
                    )
                    candidate["retrieval_engine"] = "giant_partial_anchor"
                    candidate["span_match_type"] = match_mode
                    candidate["token_subsequence_coverage"] = round(coverage * 100, 2)
                    candidate["giant_partial_expansion_ayahs"] = expansion
                    seen.add(key)
                    candidates.append(candidate)

        return self._rank_candidates(candidates, top_k=top_k)

    def _find_giant_exact_candidates_for_mode(
        self,
        *,
        query: str,
        light_query: str,
        aggressive_query: str,
        light_query_tokens: list[str],
        aggressive_query_tokens: list[str],
        scope_order: list[int],
        anchor_size: int,
        min_window_size: int,
        top_k: int,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()

        mode_specs = (
            (
                "anchor_ngram_light",
                light_query_tokens,
                "light_tokens",
                "light_token_ayahs",
                "light_ngram_positions",
            ),
            (
                "anchor_ngram_aggressive",
                aggressive_query_tokens,
                "aggressive_tokens",
                "aggressive_token_ayahs",
                "aggressive_ngram_positions",
            ),
        )

        for match_mode, query_tokens, tokens_attr, ayahs_attr, ngram_attr in mode_specs:
            if len(query_tokens) < anchor_size * 2:
                continue

            prefix_anchor = tuple(query_tokens[:anchor_size])
            suffix_anchor = tuple(query_tokens[-anchor_size:])
            middle_offset = max((len(query_tokens) // 2) - (anchor_size // 2), 0)
            middle_anchor = tuple(query_tokens[middle_offset : middle_offset + anchor_size])

            for surah_no in scope_order:
                index = self.surah_index.get(surah_no)
                if index is None:
                    continue

                surah_tokens = getattr(index, tokens_attr)
                surah_token_ayahs = getattr(index, ayahs_attr)
                ngram_positions: dict[tuple[str, ...], list[int]] = getattr(index, ngram_attr)

                prefix_positions = ngram_positions.get(prefix_anchor, [])
                if not prefix_positions:
                    continue

                suffix_position_set = set(ngram_positions.get(suffix_anchor, []))
                middle_position_set = set(ngram_positions.get(middle_anchor, [])) if middle_anchor else set()
                max_positions = min(len(prefix_positions), 64)

                for start_token_idx in prefix_positions[:max_positions]:
                    end_anchor_idx = start_token_idx + len(query_tokens) - anchor_size
                    if end_anchor_idx not in suffix_position_set:
                        continue

                    if middle_anchor:
                        expected_middle_idx = start_token_idx + middle_offset
                        if expected_middle_idx not in middle_position_set:
                            continue

                    end_token_idx = start_token_idx + len(query_tokens)
                    if end_token_idx > len(surah_tokens):
                        continue

                    if surah_tokens[start_token_idx:end_token_idx] != query_tokens:
                        continue

                    ayah_start = surah_token_ayahs[start_token_idx]
                    ayah_end = surah_token_ayahs[end_token_idx - 1]
                    if ayah_start is None or ayah_end is None:
                        continue
                    if ayah_end - ayah_start + 1 < min_window_size:
                        continue

                    row = self._get_dynamic_row(surah_no, ayah_start, ayah_end)
                    key = row["canonical_source_id"]
                    if key in seen:
                        continue

                    candidate = self._build_exact_match_candidate(
                        query=query,
                        light_query=light_query,
                        aggressive_query=aggressive_query,
                        row=row,
                        retrieval_engine="giant_exact_anchor",
                        span_match_type=match_mode,
                        anchor_size=anchor_size,
                        anchor_start_token_idx=start_token_idx,
                    )
                    seen.add(key)
                    candidates.append(candidate)

                    if len(candidates) >= top_k:
                        return self._rank_candidates(candidates, top_k=top_k)

        return self._rank_candidates(candidates, top_k=top_k)

    def _collect_seed_ranges(
        self,
        *,
        ayah_seed_candidates: list[dict[str, Any]],
        passage_seed_candidates: list[dict[str, Any]],
    ) -> list[tuple[int, int, int]]:
        seeds: list[tuple[int, int, int]] = []
        seen: set[tuple[int, int, int]] = set()

        def add_seed(surah_no: int | None, start_ayah: int | None, end_ayah: int | None) -> None:
            if surah_no is None or start_ayah is None or end_ayah is None:
                return
            key = (int(surah_no), int(start_ayah), int(end_ayah))
            if key not in seen:
                seen.add(key)
                seeds.append(key)

        for candidate in passage_seed_candidates[:5]:
            row = candidate.get("row") or {}
            add_seed(row.get("surah_no"), row.get("start_ayah"), row.get("end_ayah"))

        for candidate in ayah_seed_candidates[:5]:
            row = candidate.get("row") or {}
            ayah_no = row.get("ayah_no")
            add_seed(row.get("surah_no"), ayah_no, ayah_no)

        return seeds[:5]

    def _find_token_subsequence_seed_candidates(
        self,
        query: str,
        *,
        seed_ranges: list[tuple[int, int, int]],
        min_window_size: int,
        top_k: int,
    ) -> list[dict[str, Any]]:
        light_query = normalize_arabic_light(query)
        aggressive_query = normalize_arabic_aggressive(query)
        light_query_tokens = tokenize(light_query)
        aggressive_query_tokens = tokenize(aggressive_query)
        if len(light_query_tokens) < 8:
            return []

        seed_surahs = sorted({surah_no for surah_no, _, _ in seed_ranges})
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()

        for surah_no in seed_surahs:
            index = self.surah_index.get(surah_no)
            if not index:
                continue

            for match_mode, query_tokens, surah_tokens, token_ayahs, token_positions in (
                ("token_subsequence_light", light_query_tokens, index.light_tokens, index.light_token_ayahs, index.light_token_positions),
                ("token_subsequence_aggressive", aggressive_query_tokens, index.aggressive_tokens, index.aggressive_token_ayahs, index.aggressive_token_positions),
            ):
                if len(query_tokens) < 8:
                    continue
                best = self._best_token_subsequence_span(
                    query_tokens=query_tokens,
                    surah_tokens=surah_tokens,
                    surah_token_ayahs=token_ayahs,
                    token_positions=token_positions,
                )
                if not best:
                    continue

                coverage = best["coverage"]
                if coverage < 0.78:
                    continue

                ayah_start = best["ayah_start"]
                ayah_end = best["ayah_end"]
                if ayah_start is None or ayah_end is None:
                    continue
                window_size = ayah_end - ayah_start + 1
                if window_size < min_window_size:
                    continue

                row = self._get_dynamic_row(surah_no, ayah_start, ayah_end)
                candidate = compute_candidate_score(
                    normalized_query=light_query,
                    query_tokens=light_query_tokens,
                    row=row,
                    original_query=query,
                    aggressive_query=aggressive_query,
                    aggressive_query_tokens=aggressive_query_tokens,
                )
                candidate["retrieval_engine"] = "token_subsequence"
                candidate["span_match_type"] = match_mode
                candidate["token_subsequence_coverage"] = round(coverage * 100, 2)
                key = row["canonical_source_id"]
                if key not in seen:
                    seen.add(key)
                    candidates.append(candidate)

        return self._rank_candidates(candidates, top_k=top_k)

    @staticmethod
    def _best_token_subsequence_span(
        *,
        query_tokens: list[str],
        surah_tokens: list[str],
        surah_token_ayahs: list[int],
        token_positions: dict[str, list[int]],
    ) -> dict[str, Any] | None:
        if not query_tokens or not surah_tokens:
            return None

        best_anchor_q_idx = None
        best_anchor_positions: list[int] | None = None
        best_freq = None

        for q_idx, token in enumerate(query_tokens):
            positions = token_positions.get(token)
            if not positions:
                continue
            freq = len(positions)
            if best_freq is None or freq < best_freq:
                best_freq = freq
                best_anchor_q_idx = q_idx
                best_anchor_positions = positions
                if freq == 1:
                    break

        if best_anchor_positions is None or best_anchor_q_idx is None:
            return None

        best: dict[str, Any] | None = None
        max_anchor_positions = 32

        for s_idx in best_anchor_positions[:max_anchor_positions]:
            q_left = best_anchor_q_idx - 1
            s_left = s_idx - 1
            while q_left >= 0 and s_left >= 0 and query_tokens[q_left] == surah_tokens[s_left]:
                q_left -= 1
                s_left -= 1

            q_right = best_anchor_q_idx + 1
            s_right = s_idx + 1
            while q_right < len(query_tokens) and s_right < len(surah_tokens) and query_tokens[q_right] == surah_tokens[s_right]:
                q_right += 1
                s_right += 1

            matched_q_start = q_left + 1
            matched_q_end = q_right - 1
            matched_len = matched_q_end - matched_q_start + 1
            if matched_len <= 0:
                continue

            matched_s_start = s_idx - (best_anchor_q_idx - matched_q_start)
            matched_s_end = s_idx + (matched_q_end - best_anchor_q_idx)

            coverage = matched_len / max(len(query_tokens), 1)
            ayah_start = surah_token_ayahs[matched_s_start]
            ayah_end = surah_token_ayahs[matched_s_end]

            candidate = {
                "coverage": coverage,
                "matched_len": matched_len,
                "ayah_start": ayah_start,
                "ayah_end": ayah_end,
            }

            if best is None or (
                candidate["coverage"],
                candidate["matched_len"],
            ) > (
                best["coverage"],
                best["matched_len"],
            ):
                best = candidate

        return best

    def _expand_around_seed_ranges(
        self,
        query: str,
        *,
        seed_ranges: list[tuple[int, int, int]],
        min_window_size: int,
        max_window_size: int,
        top_k: int,
    ) -> list[dict[str, Any]]:
        light_query = normalize_arabic_light(query)
        aggressive_query = normalize_arabic_aggressive(query)
        light_query_tokens = tokenize(light_query)
        aggressive_query_tokens = tokenize(aggressive_query)
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()

        for surah_no, seed_start, seed_end in seed_ranges:
            rows = self.surah_rows.get(surah_no, [])
            ayah_count = len(rows)
            if ayah_count < min_window_size:
                continue

            seed_window = seed_end - seed_start + 1
            growth_budget = max(4, min(max_window_size, max_window_size - seed_window + 4))
            start_min = max(1, seed_start - growth_budget)
            start_max = min(ayah_count, seed_start + 2)
            end_min = max(1, seed_end - 2)
            end_max = min(ayah_count, seed_end + growth_budget)

            for start_ayah in range(start_min, start_max + 1):
                for end_ayah in range(max(end_min, start_ayah), end_max + 1):
                    window_size = end_ayah - start_ayah + 1
                    if window_size < min_window_size or window_size > max_window_size:
                        continue
                    row = self._get_dynamic_row(surah_no, start_ayah, end_ayah)
                    key = row["canonical_source_id"]
                    if key in seen:
                        continue
                    seen.add(key)
                    candidate = compute_candidate_score(
                        normalized_query=light_query,
                        query_tokens=light_query_tokens,
                        row=row,
                        original_query=query,
                        aggressive_query=aggressive_query,
                        aggressive_query_tokens=aggressive_query_tokens,
                    )
                    candidate["retrieval_engine"] = "local_seed_expand"
                    candidate["span_match_type"] = "seed_local_neighborhood"
                    candidates.append(candidate)

        return self._rank_candidates(candidates, top_k=top_k)

    @staticmethod
    def _rank_candidates(candidates: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        candidates.sort(
            key=lambda x: (
                x.get("score", 0.0),
                x.get("exact_normalized_light", 0.0),
                x.get("contains_query_in_text_light", 0.0),
                x.get("token_coverage", 0.0),
                x.get("token_subsequence_coverage", 0.0),
            ),
            reverse=True,
        )
        return candidates[:top_k]

    @staticmethod
    def _map_char_span_to_ayahs(
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
