from __future__ import annotations

from shared.utils.lexical import field_score, normalize_search_text


def score_tafsir_row(row, normalized_query: str, query_tokens: list[str]) -> tuple[float, tuple[str, ...]]:
    surah_label = f"surah {int(row.surah_no)}" if getattr(row, 'surah_no', None) is not None else ''
    metadata_text = ' '.join(filter(None, [row.display_name, row.citation_label, surah_label, row.quran_span_ref, row.anchor_verse_key]))
    metadata = field_score(query_text=normalized_query, query_tokens=query_tokens, field_text=metadata_text, weight=1.8, allow_fuzzy=True)
    body = field_score(query_text=normalized_query, query_tokens=query_tokens, field_text=row.text_plain, weight=1.0, allow_fuzzy=False)
    score = metadata.score + body.score
    if getattr(row, 'quran_span_ref', None) and normalize_search_text(row.quran_span_ref) in normalized_query:
        score += 0.75
    matched_terms = tuple(dict.fromkeys([*metadata.matched_terms, *body.matched_terms]))
    return float(score), matched_terms
