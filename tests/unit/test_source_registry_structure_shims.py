from domains.source_registry import get_source_record as domain_get_source_record
from domains.source_registry import run_source_governance_checks as domain_run_source_governance_checks
from services.source_registry import get_source_record as service_get_source_record
from services.source_registry.invariants import run_source_governance_checks as service_run_source_governance_checks


def test_source_registry_shims_and_domain_exports_resolve() -> None:
    assert domain_get_source_record("tafsir:ibn-kathir-en") is not None
    assert service_get_source_record("tafsir:ibn-kathir-en") is not None
    assert callable(domain_run_source_governance_checks)
    assert callable(service_run_source_governance_checks)
