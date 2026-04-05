from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from domains.source_registry.db_registry import list_source_records_from_db
from domains.source_registry.registry import SOURCE_REGISTRY_BOOTSTRAP
from shared.schemas.source_record import SourceRecord


@dataclass(frozen=True)
class SourceGovernanceIssue:
    code: str
    source_id: str | None
    message: str
    severity: str = "error"


class SourceGovernanceInvariantError(RuntimeError):
    def __init__(self, issues: list[SourceGovernanceIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))


def _issue(code: str, source_id: str | None, message: str, *, severity: str = "error") -> SourceGovernanceIssue:
    return SourceGovernanceIssue(code=code, source_id=source_id, message=message, severity=severity)


def validate_source_record(record: SourceRecord) -> list[SourceGovernanceIssue]:
    issues: list[SourceGovernanceIssue] = []

    if record.default_for_explain and (not record.enabled or not record.approved_for_answering):
        issues.append(
            _issue(
                "default_requires_enabled_approved",
                record.source_id,
                f"Source {record.source_id} is marked default_for_explain but is not enabled+approved.",
            )
        )

    if record.supports_quran_composition and record.source_domain != "tafsir":
        issues.append(
            _issue(
                "quran_composition_only_for_tafsir",
                record.source_id,
                f"Source {record.source_id} supports_quran_composition but is not a tafsir source.",
            )
        )

    if record.supports_quran_composition and (not record.enabled or not record.approved_for_answering):
        issues.append(
            _issue(
                "composition_requires_enabled_approved",
                record.source_id,
                f"Source {record.source_id} supports Quran composition but is not enabled+approved.",
            )
        )

    if record.approved_for_answering and (not record.display_name or not record.citation_label):
        issues.append(
            _issue(
                "approved_requires_display_metadata",
                record.source_id,
                f"Approved source {record.source_id} is missing display_name or citation_label.",
            )
        )

    if record.priority_rank < 0:
        issues.append(
            _issue(
                "priority_rank_non_negative",
                record.source_id,
                f"Source {record.source_id} has a negative priority_rank.",
            )
        )

    return issues


def validate_source_records(records: Iterable[SourceRecord]) -> list[SourceGovernanceIssue]:
    records = list(records)
    issues: list[SourceGovernanceIssue] = []
    by_domain: dict[str, list[SourceRecord]] = {}
    for record in records:
        issues.extend(validate_source_record(record))
        by_domain.setdefault(record.source_domain, []).append(record)

    for domain, domain_records in by_domain.items():
        defaults = [
            record
            for record in domain_records
            if record.default_for_explain and record.enabled and record.approved_for_answering
        ]
        if len(defaults) > 1:
            issues.append(
                _issue(
                    "multiple_defaults_for_domain",
                    None,
                    f"Source domain {domain} has multiple enabled+approved defaults_for_explain: {[record.source_id for record in defaults]}",
                )
            )

        if domain == "tafsir":
            eligible = [
                record
                for record in domain_records
                if record.enabled and record.approved_for_answering and record.supports_quran_composition
            ]
            if eligible and not defaults:
                issues.append(
                    _issue(
                        "no_default_tafsir_for_explain",
                        None,
                        "No enabled+approved default Tafsir source is configured for explain-mode selection.",
                        severity="warning",
                    )
                )

        if domain == "quran":
            eligible_text = [
                record
                for record in domain_records
                if record.enabled and record.approved_for_answering and record.source_kind == "canonical_text"
            ]
            if not eligible_text:
                issues.append(
                    _issue(
                        "no_enabled_quran_text_source",
                        None,
                        "No enabled+approved Quran canonical text source is configured.",
                        severity="warning",
                    )
                )

            eligible_translation = [
                record
                for record in domain_records
                if record.enabled and record.approved_for_answering and record.source_kind == "translation"
            ]
            if not eligible_translation:
                issues.append(
                    _issue(
                        "no_enabled_quran_translation_source",
                        None,
                        "No enabled+approved Quran translation source is configured.",
                        severity="warning",
                    )
                )

    return issues


def load_governed_source_records(*, database_url: str | None = None) -> list[SourceRecord]:
    bootstrap = list(SOURCE_REGISTRY_BOOTSTRAP.values())
    db_records = list_source_records_from_db(database_url=database_url)
    merged: dict[str, SourceRecord] = {record.source_id: record for record in bootstrap}
    for record in db_records:
        merged[record.source_id] = record
    return list(merged.values())


def run_source_governance_checks(*, database_url: str | None = None, strict: bool = False) -> list[SourceGovernanceIssue]:
    issues = validate_source_records(load_governed_source_records(database_url=database_url))
    if strict and any(issue.severity == "error" for issue in issues):
        raise SourceGovernanceInvariantError([issue for issue in issues if issue.severity == "error"])
    return issues
