from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

MULTISPACE_RE = re.compile(r"\s+")
NON_WORD_RE = re.compile(r"[^\w\s:]+", re.UNICODE)

_STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'of', 'in', 'on', 'to', 'for', 'from', 'with',
    'what', 'which', 'who', 'whom', 'whose', 'is', 'are', 'was', 'were', 'be', 'been',
    'about', 'show', 'tell', 'me', 'does', 'do', 'did', 'there', 'any', 'this', 'that',
    'these', 'those', 'it', 'its', 'can', 'could', 'would', 'should', 'explain', 'please',
}

_CANONICAL_TOKEN_MAP: dict[str, str] = {
    'angry': 'anger',
    'anger': 'anger',
    'provision': 'rizq',
    'provisions': 'rizq',
    'sustenance': 'rizq',
    'livelihood': 'rizq',
    'rizk': 'rizq',
    'rizq': 'rizq',
    'رزق': 'rizq',
}

_SYNONYMS: dict[str, set[str]] = {
    'sabr': {'patience'},
    'patience': {'sabr'},
    'niyyah': {'intention', 'intentions'},
    'intention': {'niyyah', 'intentions'},
    'intentions': {'niyyah', 'intention'},
    'taqwa': {'piety', 'godconsciousness', 'god-consciousness'},
    'piety': {'taqwa'},
    'rizq': {'provision', 'provisions', 'sustenance', 'livelihood'},
    'provision': {'rizq', 'sustenance', 'livelihood'},
    'sustenance': {'rizq', 'provision', 'livelihood'},
    'livelihood': {'rizq', 'provision', 'sustenance'},
    'tawakkul': {'reliance', 'trust'},
    'reliance': {'tawakkul'},
    'iman': {'faith'},
    'faith': {'iman'},
    'mercy': {'rahmah'},
    'rahmah': {'mercy'},
    'hardship': {'difficulty'},
    'difficulty': {'hardship'},
    'anger': {'angry', 'do not get angry', "don't get angry"},
    'angry': {'anger', 'do not get angry', "don't get angry"},
}

_CONCEPT_PHRASES: dict[str, tuple[str, ...]] = {
    'anger': ('do not get angry', "don't get angry"),
    'rizq': ('sustenance', 'livelihood', 'provisions', 'provision'),
}


@dataclass(frozen=True)
class FieldScore:
    score: float
    matched_terms: tuple[str, ...]


def canonicalize_search_token(token: str) -> str:
    return _CANONICAL_TOKEN_MAP.get(token, token)


def concept_phrases_for_tokens(tokens: Iterable[str]) -> tuple[str, ...]:
    phrases: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        canonical = canonicalize_search_token(token)
        for phrase in _CONCEPT_PHRASES.get(canonical, ()):
            if phrase not in seen:
                phrases.append(phrase)
                seen.add(phrase)
    return tuple(phrases)


def normalize_search_text(text: str | None) -> str:
    value = (text or '').casefold().replace('_', ' ')
    value = NON_WORD_RE.sub(' ', value)
    value = MULTISPACE_RE.sub(' ', value).strip()
    return value


def tokenize_search_text(text: str | None) -> list[str]:
    normalized = normalize_search_text(text)
    tokens = [canonicalize_search_token(token) for token in normalized.split(' ') if token and (token not in _STOPWORDS or token.isdigit())]
    if tokens:
        return tokens
    return [canonicalize_search_token(token) for token in normalized.split(' ') if token]


def expand_query_tokens(tokens: Iterable[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for raw_token in tokens:
        token = canonicalize_search_token(raw_token)
        if token not in seen:
            expanded.append(token)
            seen.add(token)
        for synonym in _SYNONYMS.get(token, set()):
            normalized_synonym = normalize_search_text(synonym)
            if ' ' in normalized_synonym:
                if normalized_synonym not in seen:
                    expanded.append(normalized_synonym)
                    seen.add(normalized_synonym)
                continue
            canonical_synonym = canonicalize_search_token(normalized_synonym)
            if canonical_synonym not in seen:
                expanded.append(canonical_synonym)
                seen.add(canonical_synonym)
    return expanded


def trigram_similarity(left: str | None, right: str | None) -> float:
    a = normalize_search_text(left)
    b = normalize_search_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    a_trigrams = _trigrams(a)
    b_trigrams = _trigrams(b)
    if not a_trigrams or not b_trigrams:
        return 0.0
    overlap = len(a_trigrams & b_trigrams)
    union = len(a_trigrams | b_trigrams)
    return float(overlap / union) if union else 0.0


def field_score(*, query_text: str, query_tokens: list[str], field_text: str | None, weight: float, allow_fuzzy: bool = False) -> FieldScore:
    normalized_field = normalize_search_text(field_text)
    normalized_query = normalize_search_text(query_text)
    if not normalized_field:
        return FieldScore(score=0.0, matched_terms=())

    field_tokens = tokenize_search_text(normalized_field)
    field_token_set = set(field_tokens)
    matched_terms: list[str] = []
    token_hits = 0
    fuzzy_bonus = 0.0

    for token in query_tokens:
        if token in field_token_set or token in normalized_field:
            matched_terms.append(token)
            token_hits += 1
            continue
        if allow_fuzzy and len(token) >= 4:
            best = 0.0
            for candidate in field_token_set:
                if abs(len(candidate) - len(token)) > 4:
                    continue
                similarity = trigram_similarity(token, candidate)
                if similarity > best:
                    best = similarity
            if best >= 0.45:
                matched_terms.append(token)
                fuzzy_bonus += best

    if not query_tokens:
        return FieldScore(score=0.0, matched_terms=())

    coverage = token_hits / len(query_tokens)
    score = weight * coverage * 4.0
    score += weight * fuzzy_bonus
    if normalized_query and len(normalized_query) > 3 and normalized_query in normalized_field:
        score += weight * 2.0
    return FieldScore(score=float(score), matched_terms=tuple(dict.fromkeys(matched_terms)))


def build_snippet(text: str | None, *, query_text: str, max_length: int = 220) -> str:
    normalized_query = normalize_search_text(query_text)
    value = (text or '').strip()
    if not value:
        return ''
    if len(value) <= max_length:
        return value

    lowered = normalize_search_text(value)
    match_at = lowered.find(normalized_query) if normalized_query else -1
    if match_at < 0:
        tokens = tokenize_search_text(query_text)
        for token in tokens:
            match_at = lowered.find(token)
            if match_at >= 0:
                break
    if match_at < 0:
        return value[: max_length - 1].rstrip() + '…'

    start = max(0, match_at - 60)
    end = min(len(value), start + max_length)
    snippet = value[start:end].strip()
    if start > 0:
        snippet = '…' + snippet
    if end < len(value):
        snippet = snippet.rstrip() + '…'
    return snippet


def _trigrams(value: str) -> set[str]:
    padded = f"  {value}  "
    return {padded[index:index + 3] for index in range(len(padded) - 2)}
