from shared.schemas.source_record import SourceRecord
from services.source_registry.invariants import run_source_governance_checks, validate_source_records
from services.source_registry.registry import get_default_tafsir_source_for_explain, resolve_tafsir_source_for_explain


def test_validate_source_records_flags_inconsistent_default_source():
    issues = validate_source_records(
        [
            SourceRecord(
                source_id="tafsir:test",
                source_domain="tafsir",
                source_kind="commentary",
                display_name="Test Tafsir",
                citation_label="Test Tafsir",
                language="en",
                enabled=False,
                approved_for_answering=False,
                default_for_explain=True,
                supports_quran_composition=True,
                priority_rank=10,
            )
        ]
    )

    codes = {issue.code for issue in issues}
    assert "default_requires_enabled_approved" in codes
    assert "composition_requires_enabled_approved" in codes


def test_run_source_governance_checks_on_bootstrap_has_no_errors():
    issues = run_source_governance_checks()
    assert not [issue for issue in issues if issue.severity == "error"]


def test_resolve_requested_tafsir_source_rejects_disabled_or_unapproved_source(monkeypatch):
    disabled = SourceRecord(
        source_id="tafsir:test-disabled",
        source_domain="tafsir",
        source_kind="commentary",
        display_name="Disabled Tafsir",
        citation_label="Disabled Tafsir",
        language="en",
        enabled=False,
        approved_for_answering=False,
        default_for_explain=True,
        supports_quran_composition=True,
        priority_rank=10,
    )

    monkeypatch.setattr("services.source_registry.registry.get_source_record", lambda *args, **kwargs: disabled)
    assert resolve_tafsir_source_for_explain("tafsir:test-disabled") is None


def test_default_tafsir_source_still_resolves_from_bootstrap():
    selected = get_default_tafsir_source_for_explain()
    assert selected is not None
    assert selected.source_id == "tafsir:ibn-kathir-en"
