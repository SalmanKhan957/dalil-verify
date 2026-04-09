from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from shared.utils.lexical import normalize_search_text, tokenize_search_text

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ASSET_PATH = _REPO_ROOT / 'assets' / 'query_intelligence' / 'hadith_topic_families.v1.json'

_MORAL_SLUGS = {
    'anger', 'patience', 'hasad', 'jealousy', 'lying', 'truthfulness', 'backbiting',
    'arrogance', 'mercy', 'forgiveness', 'sincerity', 'speech', 'family conduct', 'family_conduct',
}
_RITUAL_CUES = {'prayer', 'salah', 'fasting', 'sawm', 'wudu', 'ablution', 'zakat', 'hajj', 'umrah', 'tayammum'}
_ENTITY_CUES = {'dajjal', 'hour', 'fitan', 'mahdi', 'gog', 'magog', 'yajuj', 'majuj', 'tribulations'}
_NARRATIVE_CUES = {'story', 'incident', 'event', 'battle', 'happened', 'visit'}


@dataclass(frozen=True, slots=True)
class HadithTopicFamilyDecision:
    family_id: str
    retrieval_strategy: str
    confidence: float
    matched_aliases: tuple[str, ...] = ()
    entity_slug: str | None = None
    allow_generic_fallback: bool = False
    debug: dict[str, object] | None = None


@lru_cache(maxsize=1)
def _load_family_payload() -> dict[str, dict[str, object]]:
    payload = json.loads(_ASSET_PATH.read_text(encoding='utf-8'))
    families: dict[str, dict[str, object]] = {}
    for item in payload.get('families', []):
        family_id = str(item['family_id'])
        aliases = tuple(normalize_search_text(value) for value in item.get('aliases', []))
        families[family_id] = {
            'family_id': family_id,
            'retrieval_strategy': str(item.get('retrieval_strategy') or 'guidance_units'),
            'allow_generic_fallback': bool(item.get('allow_generic_fallback', False)),
            'aliases': aliases,
        }
    return families


def _best_aliases(normalized_query: str, family_id: str) -> tuple[str, ...]:
    family = _load_family_payload().get(family_id) or {}
    aliases = tuple(family.get('aliases') or ())
    return tuple(alias for alias in aliases if alias and alias in normalized_query)


def classify_hadith_topic_family(query) -> HadithTopicFamilyDecision:
    normalized_query = normalize_search_text(getattr(query, 'normalized_query', None) or getattr(query, 'raw_query', '') or '')
    tokens = set(tokenize_search_text(normalized_query))
    topic_candidates = {str(value).casefold() for value in getattr(query, 'topic_candidates', ())}
    query_profile = str(getattr(query, 'query_profile', '') or '')

    entity_aliases = _best_aliases(normalized_query, 'entity_eschatology')
    if entity_aliases or (tokens & _ENTITY_CUES):
        alias = entity_aliases[0] if entity_aliases else sorted(tokens & _ENTITY_CUES)[0]
        return HadithTopicFamilyDecision(
            family_id='entity_eschatology',
            retrieval_strategy='thematic_passages',
            confidence=0.91 if entity_aliases else 0.82,
            matched_aliases=entity_aliases or (alias,),
            entity_slug=alias.replace(' ', '_'),
            allow_generic_fallback=False,
            debug={'normalized_query': normalized_query, 'tokens': sorted(tokens), 'topic_candidates': sorted(topic_candidates)},
        )

    ritual_aliases = _best_aliases(normalized_query, 'ritual_practice')
    if ritual_aliases or (tokens & _RITUAL_CUES):
        return HadithTopicFamilyDecision(
            family_id='ritual_practice',
            retrieval_strategy='thematic_passages',
            confidence=0.82 if ritual_aliases else 0.76,
            matched_aliases=ritual_aliases or tuple(sorted(tokens & _RITUAL_CUES)),
            allow_generic_fallback=False,
            debug={'normalized_query': normalized_query, 'tokens': sorted(tokens), 'topic_candidates': sorted(topic_candidates)},
        )

    narrative_aliases = _best_aliases(normalized_query, 'narrative_event')
    if narrative_aliases or (tokens & _NARRATIVE_CUES):
        return HadithTopicFamilyDecision(
            family_id='narrative_event',
            retrieval_strategy='thematic_passages',
            confidence=0.76,
            matched_aliases=narrative_aliases or tuple(sorted(tokens & _NARRATIVE_CUES)),
            allow_generic_fallback=False,
            debug={'normalized_query': normalized_query, 'tokens': sorted(tokens), 'topic_candidates': sorted(topic_candidates)},
        )

    moral_aliases = _best_aliases(normalized_query, 'moral_guidance')
    if moral_aliases or (topic_candidates & _MORAL_SLUGS) or query_profile in {'prophetic_guidance', 'guidance', 'warning', 'virtue'}:
        return HadithTopicFamilyDecision(
            family_id='moral_guidance',
            retrieval_strategy='guidance_units',
            confidence=0.78 if moral_aliases or (topic_candidates & _MORAL_SLUGS) else 0.68,
            matched_aliases=moral_aliases or tuple(sorted(topic_candidates & _MORAL_SLUGS)),
            entity_slug=(next(iter(topic_candidates & _MORAL_SLUGS), None) or None),
            allow_generic_fallback=True,
            debug={'normalized_query': normalized_query, 'tokens': sorted(tokens), 'topic_candidates': sorted(topic_candidates)},
        )

    return HadithTopicFamilyDecision(
        family_id='moral_guidance',
        retrieval_strategy='guidance_units',
        confidence=0.55,
        matched_aliases=(),
        entity_slug=None,
        allow_generic_fallback=True,
        debug={'normalized_query': normalized_query, 'tokens': sorted(tokens), 'topic_candidates': sorted(topic_candidates)},
    )
