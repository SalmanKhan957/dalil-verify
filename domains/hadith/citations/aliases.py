from __future__ import annotations

from domains.query_intelligence.normalization import normalize_hadith_collection_alias
from shared.utils.lexical import trigram_similarity

_COLLECTION_ALIASES = {
    'bukhari': 'sahih-al-bukhari-en',
    'bukari': 'sahih-al-bukhari-en',
    'bokhari': 'sahih-al-bukhari-en',
    'sahih bukhari': 'sahih-al-bukhari-en',
    'sahih al bukhari': 'sahih-al-bukhari-en',
    'sahih al-bukhari': 'sahih-al-bukhari-en',
    'imam bukhari': 'sahih-al-bukhari-en',
    'imam bukari': 'sahih-al-bukhari-en',
    'imam bokhari': 'sahih-al-bukhari-en',
}


def resolve_collection_alias(text: str) -> str | None:
    normalized = normalize_hadith_collection_alias(text)
    if not normalized:
        return None
    exact = _COLLECTION_ALIASES.get(normalized)
    if exact is not None:
        return exact

    best_slug: str | None = None
    best_similarity = 0.0
    for alias, slug in _COLLECTION_ALIASES.items():
        similarity = trigram_similarity(normalized, alias)
        if similarity > best_similarity:
            best_similarity = similarity
            best_slug = slug
    if best_similarity >= 0.62:
        return best_slug
    return None
