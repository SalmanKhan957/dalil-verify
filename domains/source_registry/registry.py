from __future__ import annotations

from shared.schemas.source_record import SourceRecord
from domains.source_registry.db_registry import get_source_record_from_db, list_source_records_from_db, merge_source_records


SOURCE_REGISTRY_BOOTSTRAP: dict[str, SourceRecord] = {
    "quran:tanzil-simple": SourceRecord(
        source_id="quran:tanzil-simple",
        source_domain="quran",
        source_kind="canonical_text",
        display_name="Quran Arabic Canonical Text (Simple)",
        citation_label="Quran",
        language="ar",
        enabled=True,
        approved_for_answering=True,
        default_for_explain=False,
        supports_quran_composition=False,
        priority_rank=10,
        policy_note="Canonical Arabic Quran text used for deterministic lookup and verification.",
    ),
    "quran:towards-understanding-en": SourceRecord(
        source_id="quran:towards-understanding-en",
        source_domain="quran",
        source_kind="translation",
        display_name="Towards Understanding the Quran",
        citation_label="Towards Understanding the Quran",
        language="en",
        enabled=True,
        approved_for_answering=True,
        default_for_explain=False,
        supports_quran_composition=False,
        priority_rank=20,
        policy_note="English translation attached to Quran spans for bounded explanation flows.",
    ),
    "tafsir:ibn-kathir-en": SourceRecord(
        source_id="tafsir:ibn-kathir-en",
        source_domain="tafsir",
        source_kind="commentary",
        display_name="Tafsir Ibn Kathir (English)",
        citation_label="Tafsir Ibn Kathir",
        language="en",
        enabled=True,
        approved_for_answering=True,
        default_for_explain=True,
        supports_quran_composition=True,
        priority_rank=10,
        upstream_resource_id=169,
        policy_note="Approved bounded Tafsir source for Quran span explanation and commentary-backed answer composition.",
    ),
    "hadith:sahih-bukhari-en": SourceRecord(
        source_id="hadith:sahih-bukhari-en",
        source_domain="hadith",
        source_kind="hadith_collection",
        display_name="Sahih al-Bukhari (English)",
        citation_label="Sahih al-Bukhari",
        language="en",
        enabled=False,
        approved_for_answering=False,
        default_for_explain=False,
        supports_quran_composition=False,
        priority_rank=1000,
        policy_note="Planned Hadith domain placeholder until canonical ingestion and grading metadata are implemented.",
    ),
}

# Backwards-compatible alias for existing imports.
SOURCE_REGISTRY = SOURCE_REGISTRY_BOOTSTRAP


def _bootstrap_records() -> list[SourceRecord]:
    return list(SOURCE_REGISTRY_BOOTSTRAP.values())


def get_source_record(source_id: str, *, database_url: str | None = None) -> SourceRecord | None:
    db_record = get_source_record_from_db(source_id, database_url=database_url)
    if db_record is not None:
        return db_record
    return SOURCE_REGISTRY_BOOTSTRAP.get(source_id)


def is_source_enabled(source_id: str, *, database_url: str | None = None) -> bool:
    source = get_source_record(source_id, database_url=database_url)
    return bool(source and source.enabled and source.approved_for_answering)


def get_source_records_by_domain(source_domain: str, *, database_url: str | None = None) -> list[SourceRecord]:
    bootstrap = [source for source in _bootstrap_records() if source.source_domain == source_domain]
    db_records = list_source_records_from_db(source_domain, database_url=database_url)
    merged = merge_source_records(bootstrap, db_records)
    return sorted(merged, key=lambda record: (record.priority_rank, record.source_id))


def _eligible_tafsir_sources(*, database_url: str | None = None) -> list[SourceRecord]:
    return [
        source
        for source in get_source_records_by_domain("tafsir", database_url=database_url)
        if source.enabled and source.approved_for_answering and source.supports_quran_composition
    ]


def get_default_tafsir_source_for_explain(*, database_url: str | None = None) -> SourceRecord | None:
    eligible = _eligible_tafsir_sources(database_url=database_url)
    if not eligible:
        return None

    defaults = [source for source in eligible if source.default_for_explain]
    pool = defaults or eligible
    return sorted(pool, key=lambda source: (source.priority_rank, source.source_id))[0]


def resolve_tafsir_source_for_explain(
    requested_source_id: str | None,
    *,
    database_url: str | None = None,
) -> SourceRecord | None:
    if requested_source_id:
        source = get_source_record(requested_source_id, database_url=database_url)
        if source is None or source.source_domain != "tafsir":
            return None
        if not (source.enabled and source.approved_for_answering and source.supports_quran_composition):
            return None
        return source
    return get_default_tafsir_source_for_explain(database_url=database_url)
