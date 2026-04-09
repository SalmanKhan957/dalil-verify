from __future__ import annotations

import re

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


def normalize_user_query(query: str | None) -> str:
    text = MULTISPACE_RE.sub(' ', (query or '').strip())
    if not text:
        return ''
    text = _apply_token_replacements(text)
    for pattern, replacement in _MULTIWORD_REPLACEMENTS:
        text = pattern.sub(replacement, text)
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
