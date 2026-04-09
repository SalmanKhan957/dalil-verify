from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from domains.query_intelligence.models import ConceptDefinition, QueryFamilyDefinition

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ASSET_ROOT = _REPO_ROOT / 'assets' / 'query_intelligence'


def _load_json(filename: str) -> dict:
    with (_ASSET_ROOT / filename).open('r', encoding='utf-8') as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_query_family_definitions() -> tuple[QueryFamilyDefinition, ...]:
    payload = _load_json('query_families.v1.json')
    families = []
    for item in payload.get('families', []):
        families.append(
            QueryFamilyDefinition(
                family_id=str(item['family_id']),
                domain=str(item['domain']),
                route_type=item.get('route_type'),
                query_profile=str(item.get('query_profile') or 'general_topic'),
                public_supported=bool(item.get('public_supported', False)),
                needs_clarification=bool(item.get('needs_clarification', False)),
                cue_phrases=tuple(str(value).casefold() for value in item.get('cue_phrases', [])),
                example_queries=tuple(str(value) for value in item.get('example_queries', [])),
                domain_cues=tuple(str(value).casefold() for value in item.get('domain_cues', [])),
                priority=int(item.get('priority') or 0),
            )
        )
    return tuple(sorted(families, key=lambda item: item.priority, reverse=True))


@lru_cache(maxsize=1)
@lru_cache(maxsize=1)
def load_clarify_policies() -> tuple[dict, ...]:
    payload = _load_json('clarify_policies.v1.json')
    return tuple(dict(item) for item in payload.get('policies', []))


@lru_cache(maxsize=1)
def load_concept_definitions() -> tuple[ConceptDefinition, ...]:
    payload = _load_json('concepts.v1.json')
    concepts = []
    for item in payload.get('concepts', []):
        concepts.append(
            ConceptDefinition(
                concept_id=str(item['concept_id']),
                slug=str(item['slug']),
                domain=str(item['domain']),
                family=str(item['family']),
                label_en=str(item.get('label_en') or item['slug']),
                surface_forms=tuple(str(value).casefold() for value in item.get('surface_forms', [])),
                artifact_surface_forms=tuple(str(value).casefold() for value in item.get('artifact_surface_forms', [])),
                directive_biases=tuple(str(value) for value in item.get('directive_biases', [])),
                guidance_roles=tuple(str(value) for value in item.get('guidance_roles', [])),
                canonical_ref=str(item['canonical_ref']) if item.get('canonical_ref') else None,
            )
        )
    return tuple(concepts)
