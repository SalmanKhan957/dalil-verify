from __future__ import annotations

from collections import Counter, defaultdict
from math import log
from typing import Any, Iterable

from scripts.common.text_normalization import (
    normalize_arabic_aggressive,
    normalize_arabic_light,
    tokenize,
)


def _extract_qgrams(text: str, q: int = 3) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= q:
        return [text]
    return [text[i : i + q] for i in range(len(text) - q + 1)]


class QuranShortlistIndex:
    """
    Lightweight in-memory shortlist index for the verifier.

    Goal:
    - keep retrieval deterministic
    - avoid brute-force fuzzy scoring over the full corpus
    - preserve current reranker/fusion behavior by only changing candidate generation
    """

    def __init__(
        self,
        rows: list[dict[str, Any]],
        *,
        qgram_size: int = 3,
    ) -> None:
        self.rows = rows
        self.row_count = len(rows)
        self.qgram_size = qgram_size

        self.exact_light: dict[str, list[int]] = defaultdict(list)
        self.exact_aggressive: dict[str, list[int]] = defaultdict(list)

        self.token_postings_light: dict[str, list[int]] = defaultdict(list)
        self.token_postings_aggressive: dict[str, list[int]] = defaultdict(list)
        self.token_idf_light: dict[str, float] = {}
        self.token_idf_aggressive: dict[str, float] = {}

        self.qgram_postings: dict[str, list[int]] = defaultdict(list)
        self.qgram_idf: dict[str, float] = {}

        self._build()

    def _build(self) -> None:
        token_df_light: Counter[str] = Counter()
        token_df_aggressive: Counter[str] = Counter()
        qgram_df: Counter[str] = Counter()

        for idx, row in enumerate(self.rows):
            text_light = row.get("text_normalized_light") or ""
            text_aggressive = row.get("text_normalized_aggressive") or ""

            self.exact_light[text_light].append(idx)
            self.exact_aggressive[text_aggressive].append(idx)

            tokens_light = set(row.get("tokens_light") or tokenize(text_light))
            tokens_aggressive = set(row.get("tokens_aggressive") or tokenize(text_aggressive))

            for token in tokens_light:
                self.token_postings_light[token].append(idx)
                token_df_light[token] += 1

            for token in tokens_aggressive:
                self.token_postings_aggressive[token].append(idx)
                token_df_aggressive[token] += 1

            qgrams = set(_extract_qgrams(text_aggressive, self.qgram_size))
            for qg in qgrams:
                self.qgram_postings[qg].append(idx)
                qgram_df[qg] += 1

        self.token_idf_light = {
            token: self._idf(df) for token, df in token_df_light.items()
        }
        self.token_idf_aggressive = {
            token: self._idf(df) for token, df in token_df_aggressive.items()
        }
        self.qgram_idf = {qg: self._idf(df) for qg, df in qgram_df.items()}

    def _idf(self, df: int) -> float:
        return log(1.0 + ((self.row_count - df + 0.5) / (df + 0.5)))

    def shortlist_rows(
        self,
        query: str,
        *,
        limit: int = 250,
        allow_exact_shortcircuit: bool = True,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        light_query = normalize_arabic_light(query)
        aggressive_query = normalize_arabic_aggressive(query)

        light_tokens = list(dict.fromkeys(tokenize(light_query)))
        aggressive_tokens = list(dict.fromkeys(tokenize(aggressive_query)))

        exact_indices = set(self.exact_light.get(light_query, []))
        exact_indices.update(self.exact_aggressive.get(aggressive_query, []))

        if exact_indices and allow_exact_shortcircuit:
            ordered = sorted(exact_indices)
            return [self.rows[i] for i in ordered[:limit]], {
                "strategy": "exact",
                "candidate_count": len(ordered[:limit]),
                "exact_hit_count": len(exact_indices),
                "token_candidate_count": len(exact_indices),
                "qgram_candidate_count": 0,
            }

        combined_scores: defaultdict[int, float] = defaultdict(float)
        token_overlap_counts: defaultdict[int, int] = defaultdict(int)

        for token in light_tokens:
            weight = self.token_idf_light.get(token, 0.0)
            for idx in self.token_postings_light.get(token, []):
                combined_scores[idx] += weight
                token_overlap_counts[idx] += 1

        for token in aggressive_tokens:
            weight = self.token_idf_aggressive.get(token, 0.0) * 0.65
            for idx in self.token_postings_aggressive.get(token, []):
                combined_scores[idx] += weight
                token_overlap_counts[idx] += 1

        min_token_overlap = self._min_token_overlap(len(light_tokens))
        token_candidates = {
            idx
            for idx, overlap_count in token_overlap_counts.items()
            if overlap_count >= min_token_overlap
        }

        qgram_scores: defaultdict[int, float] = defaultdict(float)
        qgram_overlap_counts: defaultdict[int, int] = defaultdict(int)

        use_qgrams = len(aggressive_query) >= 14 or len(token_candidates) < max(20, limit // 5)
        if use_qgrams:
            for qg in set(_extract_qgrams(aggressive_query, self.qgram_size)):
                weight = self.qgram_idf.get(qg, 0.0)
                for idx in self.qgram_postings.get(qg, []):
                    qgram_scores[idx] += weight
                    qgram_overlap_counts[idx] += 1

        min_qgram_overlap = self._min_qgram_overlap(len(_extract_qgrams(aggressive_query, self.qgram_size)))
        qgram_candidates = {
            idx
            for idx, overlap_count in qgram_overlap_counts.items()
            if overlap_count >= min_qgram_overlap
        }

        candidate_pool = token_candidates | qgram_candidates

        if not candidate_pool:
            candidate_pool = set(combined_scores.keys()) | set(qgram_scores.keys())

        ranked_indices = sorted(
            candidate_pool,
            key=lambda idx: (
                combined_scores.get(idx, 0.0) + (0.35 * qgram_scores.get(idx, 0.0)),
                token_overlap_counts.get(idx, 0),
                qgram_overlap_counts.get(idx, 0),
            ),
            reverse=True,
        )[:limit]

        return [self.rows[i] for i in ranked_indices], {
            "strategy": "token_qgram",
            "candidate_count": len(ranked_indices),
            "exact_hit_count": 0,
            "token_candidate_count": len(token_candidates),
            "qgram_candidate_count": len(qgram_candidates),
            "min_token_overlap": min_token_overlap,
            "min_qgram_overlap": min_qgram_overlap,
            "used_qgrams": use_qgrams,
        }

    @staticmethod
    def _min_token_overlap(token_count: int) -> int:
        if token_count <= 2:
            return 1
        if token_count <= 4:
            return 2
        if token_count <= 8:
            return 3
        return 4

    @staticmethod
    def _min_qgram_overlap(qgram_count: int) -> int:
        if qgram_count <= 0:
            return 1
        if qgram_count <= 6:
            return 2
        if qgram_count <= 14:
            return 3
        return 4
