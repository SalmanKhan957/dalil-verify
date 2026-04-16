from __future__ import annotations

import re
from difflib import SequenceMatcher

from domains.quran.citations.surah_aliases import SURAH_CANONICAL_NAMES, resolve_surah_name

MULTISPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[A-Za-z']+")

_TOKEN_REPLACEMENTS = {
    'gve': 'give',
    'giv': 'give',
    'pls': 'please',
    'plz': 'please',
    'abt': 'about',
    'wht': 'what',
    'islams': "islam's",
    'ahadith': 'hadith',
    'ahadeeth': 'hadith',
    'ahaadith': 'hadith',
    'hadees': 'hadith',
    'hadeeth': 'hadith',
    'hadiths': 'hadith',
    'ahadiths': 'hadith',
    'bukari': 'bukhari',
    'bokhari': 'bukhari',
    'bukhارى': 'bukhari',
    'rizk': 'rizq',
    'rizq': 'rizq',
    'rizkq': 'rizq',
    'رزق': 'rizq',
}

_MULTIWORD_REPLACEMENTS = (
    (re.compile(r"\bsahi+h\s+al\s+bukhari\b", re.IGNORECASE), 'sahih al bukhari'),
    (re.compile(r"\bsahi+h\s+bukhari\b", re.IGNORECASE), 'sahih bukhari'),
    (re.compile(r"\bimam\s+bokhari\b", re.IGNORECASE), 'imam bukhari'),
    (re.compile(r"\bimam\s+bukari\b", re.IGNORECASE), 'imam bukhari'),
    (re.compile(r"\bgive\s+hadith\s+about\b", re.IGNORECASE), 'give me hadith about'),
    (re.compile(r"\bgive\s+hadith\s+on\b", re.IGNORECASE), 'give me hadith on'),
    (re.compile(r"\bgive\s+me\s+ahadith\s+about\b", re.IGNORECASE), 'give me hadith about'),
    (re.compile(r"\bgive\s+me\s+ahadith\s+on\b", re.IGNORECASE), 'give me hadith on'),
)

_COMPACT_REPLACEMENTS = (
    (re.compile(r"\bibnkathir\b", re.IGNORECASE), 'ibn kathir'),
    (re.compile(r"\bibnalkathir\b", re.IGNORECASE), 'ibn al kathir'),
    (re.compile(r"\bmaarifalquran\b", re.IGNORECASE), "ma'arif al quran"),
    (re.compile(r"\bmaarifulquran\b", re.IGNORECASE), "ma'arif ul quran"),
    (re.compile(r"\btafheemalquran\b", re.IGNORECASE), 'tafheem al quran'),
)

_COLLECTION_NUMBER_PATTERNS = (
    re.compile(r"\b(?P<name>bukhari|muslim|tirmidhi|nasai|abudawud|abu\s+dawud|ibn\s+majah|malik)(?P<number>\d{1,5})\b", re.IGNORECASE),
)

_SURAH_SCOPE_RE = re.compile(
    r"\b(?P<prefix>surah|surat|sura|soorah|sorah|chapter)\s+(?P<name>[a-z][a-z\-\s']{1,40}?)(?=(?:\s+\d{1,3}\b|\s+(?:ayah|ayahs|verse|verses)\b|[?.!,;:]|$))",
    re.IGNORECASE,
)

_TOPIC_FILLERS = (
    'please',
    'for me',
    'show me',
    'tell me',
    'give me',
    'give',
    'regarding',
)


def _replace_token(match: re.Match[str]) -> str:
    token = match.group(0)
    replacement = _TOKEN_REPLACEMENTS.get(token.casefold())
    return replacement if replacement is not None else token


def _apply_token_replacements(text: str) -> str:
    return _WORD_RE.sub(_replace_token, text)


def _apply_compact_replacements(text: str) -> str:
    for pattern, replacement in _COMPACT_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


def _split_collection_number(match: re.Match[str]) -> str:
    name = MULTISPACE_RE.sub(' ', match.group('name')).strip()
    number = match.group('number')
    return f'{name} {number}'


def _separate_collection_numbers(text: str) -> str:
    for pattern in _COLLECTION_NUMBER_PATTERNS:
        text = pattern.sub(_split_collection_number, text)
    return text




def _surah_similarity_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", '', value.casefold().replace('al', '', 1)).strip()


def _resolve_surah_name_for_normalization(name: str) -> int | None:
    direct = resolve_surah_name(name)
    if direct is not None:
        return direct
    candidate_key = _surah_similarity_key(name)
    if len(candidate_key) < 4:
        return None
    best_surah_no: int | None = None
    best_score = 0.0
    second_best = 0.0
    for surah_no, canonical_name in SURAH_CANONICAL_NAMES.items():
        score = SequenceMatcher(a=candidate_key, b=_surah_similarity_key(canonical_name)).ratio()
        if score > best_score:
            second_best = best_score
            best_score = score
            best_surah_no = surah_no
        elif score > second_best:
            second_best = score
    if best_surah_no is None or best_score < 0.76:
        return None
    if second_best and (best_score - second_best) < 0.04:
        return None
    return best_surah_no

def _canonicalize_surah_mentions(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        prefix = match.group('prefix').lower()
        name = MULTISPACE_RE.sub(' ', (match.group('name') or '').strip(" .,!?:;\"'"))
        if not name:
            return match.group(0)
        surah_no = _resolve_surah_name_for_normalization(name)
        if surah_no is None:
            return match.group(0)
        canonical_name = SURAH_CANONICAL_NAMES.get(surah_no)
        if not canonical_name:
            return match.group(0)
        return f'{prefix} {canonical_name}'

    return _SURAH_SCOPE_RE.sub(_replace, text)


def normalize_user_query(query: str | None) -> str:
    text = MULTISPACE_RE.sub(' ', (query or '').strip())
    if not text:
        return ''
    text = _apply_compact_replacements(text)
    text = _separate_collection_numbers(text)
    text = _apply_token_replacements(text)
    for pattern, replacement in _MULTIWORD_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    text = _canonicalize_surah_mentions(text)
    text = MULTISPACE_RE.sub(' ', text).strip()
    return text


def normalize_reference_query(query: str | None) -> str:
    text = normalize_user_query(query)
    text = re.sub(r"\bno\.?\s+", '', text, flags=re.IGNORECASE)
    return MULTISPACE_RE.sub(' ', text).strip(' ,:-')


def normalize_topic_query(query: str | None) -> str:
    text = normalize_user_query(query)
    if not text:
        return ''
    for filler in _TOPIC_FILLERS:
        text = re.sub(rf"\b{re.escape(filler)}\b", ' ', text, flags=re.IGNORECASE)
    text = re.sub(r"\b(in islam|about|on)\b", ' ', text, flags=re.IGNORECASE)
    text = MULTISPACE_RE.sub(' ', text).strip(' ?.!,:;-')
    return text


def normalize_hadith_collection_alias(text: str | None) -> str:
    normalized = normalize_reference_query(text)
    normalized = normalized.casefold().replace('_', ' ').replace('-', ' ')
    normalized = MULTISPACE_RE.sub(' ', normalized).strip()
    return normalized



def normalize_match_text(query: str | None) -> str:
    return normalize_user_query(query).casefold()


def normalize_compact_text(query: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", '', normalize_match_text(query))


def tokenize_match_text(query: str | None) -> tuple[str, ...]:
    normalized = normalize_match_text(query)
    if not normalized:
        return ()
    tokens: list[str] = []
    seen: set[str] = set()
    for match in _WORD_RE.finditer(normalized):
        token = match.group(0).casefold()
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tuple(tokens)
