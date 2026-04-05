from __future__ import annotations

_COLLECTION_ALIASES = {
    'bukhari': 'sahih-al-bukhari-en',
    'sahih bukhari': 'sahih-al-bukhari-en',
    'sahih al bukhari': 'sahih-al-bukhari-en',
    'sahih al-bukhari': 'sahih-al-bukhari-en',
    'imam bukhari': 'sahih-al-bukhari-en',
}


def resolve_collection_alias(text: str) -> str | None:
    normalized = ' '.join((text or '').lower().replace('_', ' ').replace('-', ' ').split())
    return _COLLECTION_ALIASES.get(normalized)
