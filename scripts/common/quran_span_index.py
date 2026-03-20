
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
    light_tokens: list[str]
    light_token_ayahs: list[int]
    light_token_positions: dict[str, list[int]]
    aggressive_tokens: list[str]
    aggressive_token_ayahs: list[int]
    aggressive_token_positions: dict[str, list[int]]


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
            self._index_exact_spans(surah_no, rows, min_window_size=5, max_window_size=12)
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
        min_window_size: int = 5,
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

    def find_long_passage_candidates(
        self,
        query: str,
        *,
        ayah_seed_candidates: list[dict[str, Any]] | None = None,
        passage_seed_candidates: list[dict[str, Any]] | None = None,
        likely_surahs: list[int] | None = None,
        min_window_size: int = 5,
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
