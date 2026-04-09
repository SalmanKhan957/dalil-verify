from __future__ import annotations

from dataclasses import dataclass

from domains.query_intelligence.catalog import load_concept_definitions


@dataclass(frozen=True, slots=True)
class TopicDefinition:
    slug: str
    family: str
    aliases: tuple[str, ...]
    directive_bias: tuple[str, ...] = ()


_HADITH_CONCEPTS = tuple(concept for concept in load_concept_definitions() if concept.domain == 'hadith')

TOPIC_DEFINITIONS: tuple[TopicDefinition, ...] = tuple(
    TopicDefinition(
        slug=concept.slug,
        family=concept.family,
        aliases=tuple(dict.fromkeys((concept.slug, concept.label_en.casefold(), *concept.surface_forms))),
        directive_bias=concept.directive_biases,
    )
    for concept in _HADITH_CONCEPTS
)

TOPIC_BY_SLUG = {definition.slug: definition for definition in TOPIC_DEFINITIONS}

ALIAS_TO_TOPIC = {
    alias.casefold(): definition.slug
    for definition in TOPIC_DEFINITIONS
    for alias in definition.aliases
}

TOPIC_FAMILIES: dict[str, tuple[str, ...]] = {}
for definition in TOPIC_DEFINITIONS:
    TOPIC_FAMILIES.setdefault(definition.family, ())
    if definition.slug not in TOPIC_FAMILIES[definition.family]:
        TOPIC_FAMILIES[definition.family] = (*TOPIC_FAMILIES[definition.family], definition.slug)


def aliases_for_topic(topic: str) -> tuple[str, ...]:
    definition = TOPIC_BY_SLUG.get(topic)
    if not definition:
        return ()
    return definition.aliases
