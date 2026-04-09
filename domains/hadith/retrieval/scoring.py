from __future__ import annotations

from shared.utils.lexical import canonicalize_search_token, concept_phrases_for_tokens, expand_query_tokens, normalize_search_text, tokenize_search_text, trigram_similarity


def _score_field(
    *,
    query_text: str,
    exact_query_tokens: list[str],
    expanded_query_tokens: list[str],
    field_text: str | None,
    weight: float,
    allow_fuzzy: bool = False,
) -> tuple[float, tuple[str, ...], int, int]:
    normalized_field = normalize_search_text(field_text)
    normalized_query = normalize_search_text(query_text)
    if not normalized_field:
        return 0.0, (), 0, 0

    field_tokens = tokenize_search_text(normalized_field)
    field_token_set = set(field_tokens)
    expanded_only_tokens = [token for token in expanded_query_tokens if token not in exact_query_tokens]

    matched_terms: list[str] = []
    direct_hits = 0
    synonym_hits = 0
    fuzzy_bonus = 0.0
    direct_occurrences = 0
    first_direct_index: int | None = None

    for token in exact_query_tokens:
        if token in field_token_set:
            direct_hits += 1
            matched_terms.append(token)
            direct_occurrences += field_tokens.count(token)
            token_index = field_tokens.index(token)
            first_direct_index = token_index if first_direct_index is None else min(first_direct_index, token_index)
            continue
        if not allow_fuzzy or len(token) < 4:
            continue
        best_similarity = 0.0
        for candidate in field_token_set:
            if abs(len(candidate) - len(token)) > 4:
                continue
            best_similarity = max(best_similarity, trigram_similarity(token, candidate))
        if best_similarity >= 0.45:
            matched_terms.append(token)
            fuzzy_bonus += best_similarity

    for token in expanded_only_tokens:
        if token in field_token_set:
            synonym_hits += 1
            matched_terms.append(token)

    denominator = max(len(exact_query_tokens), 1)
    score = 0.0
    score += weight * ((direct_hits / denominator) * 6.0)
    score += weight * ((synonym_hits / denominator) * 4.0)
    score += weight * fuzzy_bonus

    if normalized_query and normalized_query in normalized_field:
        score += weight * 3.0

    if direct_occurrences:
        score += weight * min(direct_occurrences, 3) * 0.7
        density = direct_occurrences / max(len(field_tokens), 1)
        score += weight * min(density * 40.0, 3.0)
        if first_direct_index is not None:
            score += weight * max(0.0, 1.5 - (first_direct_index / 20.0))

    return float(score), tuple(dict.fromkeys(matched_terms)), len(field_tokens), direct_occurrences


def score_hadith_row(row, normalized_query: str, query_tokens: list[str]) -> tuple[float, tuple[str, ...]]:
    exact_query_tokens = tokenize_search_text(normalized_query)
    expanded_query_tokens = expand_query_tokens(query_tokens or exact_query_tokens)
    concept_phrases = concept_phrases_for_tokens(exact_query_tokens)
    canonical_concepts = {canonicalize_search_token(token) for token in exact_query_tokens}

    metadata_text = " ".join(filter(None, [row.display_name, row.citation_label, row.canonical_ref_collection]))
    metadata_score, metadata_terms, _, _ = _score_field(
        query_text=normalized_query,
        exact_query_tokens=exact_query_tokens,
        expanded_query_tokens=expanded_query_tokens,
        field_text=metadata_text,
        weight=0.4,
        allow_fuzzy=True,
    )
    book_score, book_terms, _, _ = _score_field(
        query_text=normalized_query,
        exact_query_tokens=exact_query_tokens,
        expanded_query_tokens=expanded_query_tokens,
        field_text=row.book_title,
        weight=1.2,
        allow_fuzzy=True,
    )
    chapter_score, chapter_terms, _, _ = _score_field(
        query_text=normalized_query,
        exact_query_tokens=exact_query_tokens,
        expanded_query_tokens=expanded_query_tokens,
        field_text=row.chapter_title,
        weight=2.2,
        allow_fuzzy=True,
    )
    body_text = " ".join(filter(None, [row.english_narrator, row.english_text, row.matn_text]))
    body_score, body_terms, body_token_count, body_direct_occurrences = _score_field(
        query_text=normalized_query,
        exact_query_tokens=exact_query_tokens,
        expanded_query_tokens=expanded_query_tokens,
        field_text=body_text,
        weight=1.2,
        allow_fuzzy=False,
    )

    score = metadata_score + book_score + chapter_score + body_score

    normalized_body = normalize_search_text(body_text)
    normalized_book = normalize_search_text(row.book_title)
    normalized_chapter = normalize_search_text(row.chapter_title)
    phrase_hits: list[str] = []
    for phrase in concept_phrases:
        if phrase and phrase in normalized_body:
            score += 4.5 if ' ' in phrase else 1.5
            phrase_hits.append(phrase)

    if 'anger' in canonical_concepts:
        if 'do not get angry' in normalized_body or "don't get angry" in normalized_body:
            score += 8.0
            phrase_hits.append('do not get angry')
        incidental_markers = (
            'noticed anger on his face',
            'saw the signs of anger on his face',
            'saw anger on his face',
            'in an angry mood',
            'got angry with me',
        )
        if any(marker in normalized_body for marker in incidental_markers):
            score -= 4.0
        if body_direct_occurrences <= 1 and not phrase_hits and 'anger' not in normalized_book and 'anger' not in normalized_chapter:
            score -= 2.5

    if 'rizq' in canonical_concepts:
        rizq_markers = (
            'sustenance',
            'livelihood',
            'provision',
            'provisions',
            'provide',
            'provided',
            'expansion in his sustenance',
        )
        score += sum(1.2 for marker in rizq_markers if marker in normalized_body)
        if 'keep good relations with his kith and kin' in normalized_body or 'keep good relations with his kin' in normalized_body:
            score += 2.5

    matched_terms = tuple(dict.fromkeys([*metadata_terms, *book_terms, *chapter_terms, *body_terms, *phrase_hits]))

    if body_direct_occurrences:
        if body_token_count <= 25:
            score += 2.0
        elif body_token_count <= 50:
            score += 1.0
        elif body_token_count > 80 and body_direct_occurrences <= 1:
            score -= min((body_token_count - 80) / 25.0, 4.0)
        elif body_token_count > 140 and body_direct_occurrences <= 2:
            score -= min((body_token_count - 140) / 40.0, 2.5)

    return float(max(score, 0.0)), matched_terms
