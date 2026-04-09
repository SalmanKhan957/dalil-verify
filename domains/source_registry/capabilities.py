from __future__ import annotations

from enum import Enum

from shared.schemas.source_record import SourceRecord


class SourceCapability(str, Enum):
    EXPLICIT_LOOKUP = 'explicit_lookup'
    EXPLAIN_FROM_SOURCE = 'explain_from_source'
    TOPICAL_RETRIEVAL = 'topical_retrieval'
    COMPOSITION_ALLOWED = 'composition_allowed'
    QUOTE_VERIFICATION = 'quote_verification'
    CONVERSATION_FOLLOWUP_ANCHOR = 'conversation_followup_anchor'


_DEFAULT_CAPABILITY_ORDER = [
    SourceCapability.EXPLICIT_LOOKUP,
    SourceCapability.EXPLAIN_FROM_SOURCE,
    SourceCapability.TOPICAL_RETRIEVAL,
    SourceCapability.COMPOSITION_ALLOWED,
    SourceCapability.QUOTE_VERIFICATION,
    SourceCapability.CONVERSATION_FOLLOWUP_ANCHOR,
]


DEFAULT_SOURCE_CAPABILITIES: dict[tuple[str, str], dict[str, bool]] = {
    ('quran', 'canonical_text'): {
        SourceCapability.EXPLICIT_LOOKUP.value: True,
        SourceCapability.EXPLAIN_FROM_SOURCE.value: True,
        SourceCapability.TOPICAL_RETRIEVAL.value: False,
        SourceCapability.COMPOSITION_ALLOWED.value: False,
        SourceCapability.QUOTE_VERIFICATION.value: True,
        SourceCapability.CONVERSATION_FOLLOWUP_ANCHOR.value: True,
    },
    ('quran', 'translation'): {
        SourceCapability.EXPLICIT_LOOKUP.value: True,
        SourceCapability.EXPLAIN_FROM_SOURCE.value: True,
        SourceCapability.TOPICAL_RETRIEVAL.value: False,
        SourceCapability.COMPOSITION_ALLOWED.value: False,
        SourceCapability.QUOTE_VERIFICATION.value: False,
        SourceCapability.CONVERSATION_FOLLOWUP_ANCHOR.value: True,
    },
    ('tafsir', 'commentary'): {
        SourceCapability.EXPLICIT_LOOKUP.value: True,
        SourceCapability.EXPLAIN_FROM_SOURCE.value: True,
        SourceCapability.TOPICAL_RETRIEVAL.value: True,
        SourceCapability.COMPOSITION_ALLOWED.value: True,
        SourceCapability.QUOTE_VERIFICATION.value: False,
        SourceCapability.CONVERSATION_FOLLOWUP_ANCHOR.value: True,
    },
    ('hadith', 'hadith_collection'): {
        SourceCapability.EXPLICIT_LOOKUP.value: True,
        SourceCapability.EXPLAIN_FROM_SOURCE.value: True,
        SourceCapability.TOPICAL_RETRIEVAL.value: True,
        SourceCapability.COMPOSITION_ALLOWED.value: False,
        SourceCapability.QUOTE_VERIFICATION.value: False,
        SourceCapability.CONVERSATION_FOLLOWUP_ANCHOR.value: True,
    },
}


def _base_capabilities(record: SourceRecord) -> dict[str, bool]:
    base = dict(DEFAULT_SOURCE_CAPABILITIES.get((record.source_domain, record.source_kind), {}))
    if record.source_domain == 'tafsir':
        base[SourceCapability.COMPOSITION_ALLOWED.value] = bool(record.supports_quran_composition and record.approved_for_answering)
    if record.source_domain == 'hadith':
        base[SourceCapability.COMPOSITION_ALLOWED.value] = False
    return base


def resolve_source_capabilities(record: SourceRecord | None) -> dict[str, bool]:
    if record is None:
        return {}
    capabilities = _base_capabilities(record)
    capabilities.update({str(k): bool(v) for k, v in (record.answer_capabilities or {}).items()})
    return capabilities


def source_supports_capability(record: SourceRecord | None, capability: str | SourceCapability) -> bool:
    if record is None:
        return False
    capability_name = capability.value if isinstance(capability, SourceCapability) else str(capability)
    return bool(resolve_source_capabilities(record).get(capability_name, False))


def list_enabled_capabilities(record: SourceRecord | None) -> list[str]:
    capabilities = resolve_source_capabilities(record)
    ordered: list[str] = []
    for capability in _DEFAULT_CAPABILITY_ORDER:
        name = capability.value
        if capabilities.get(name):
            ordered.append(name)
    for name, enabled in capabilities.items():
        if enabled and name not in ordered:
            ordered.append(name)
    return ordered


def describe_hadith_answer_capability(record: SourceRecord | None) -> str | None:
    if record is None:
        return None
    if record.approved_for_answering:
        return 'full_answering'
    capabilities = resolve_source_capabilities(record)
    if capabilities.get(SourceCapability.EXPLAIN_FROM_SOURCE.value):
        return 'explicit_lookup_and_explain'
    if capabilities.get(SourceCapability.EXPLICIT_LOOKUP.value):
        return 'explicit_lookup_only'
    return None


def describe_hadith_public_response_scope(record: SourceRecord | None) -> str | None:
    if record is None:
        return None
    if record.approved_for_answering:
        return 'full_answering'
    capabilities = resolve_source_capabilities(record)
    has_explicit = bool(capabilities.get(SourceCapability.EXPLICIT_LOOKUP.value))
    has_explain = bool(capabilities.get(SourceCapability.EXPLAIN_FROM_SOURCE.value))
    has_topical = bool(capabilities.get(SourceCapability.TOPICAL_RETRIEVAL.value))
    if has_topical and (has_explicit or has_explain):
        return 'bounded_public_explicit_and_topical'
    if has_topical:
        return 'bounded_public_topical_only'
    if has_explain:
        return 'bounded_public_explicit_and_explain'
    if has_explicit:
        return 'bounded_public_explicit_only'
    return None
