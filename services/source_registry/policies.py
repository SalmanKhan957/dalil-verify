from __future__ import annotations

from shared.schemas.source_record import SourceRecord


def can_use_source_for_answering(source: SourceRecord) -> bool:
    return bool(source.enabled and source.approved_for_answering)


def can_mix_sources(primary: SourceRecord, secondary: SourceRecord) -> bool:
    if not can_use_source_for_answering(primary) or not can_use_source_for_answering(secondary):
        return False

    if primary.source_domain == secondary.source_domain:
        return True

    if {primary.source_domain, secondary.source_domain} == {"quran", "tafsir"}:
        tafsir_source = primary if primary.source_domain == "tafsir" else secondary
        return bool(tafsir_source.supports_quran_composition)

    return False
