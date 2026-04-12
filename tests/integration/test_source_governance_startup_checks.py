from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from infrastructure.db.base import Base
from infrastructure.db.models.source_work import SourceWorkORM
from services.source_registry.invariants import run_source_governance_checks
from services.source_registry.registry import get_default_tafsir_source_for_explain


def test_governance_checks_flag_inconsistent_db_overlay(tmp_path):
    database_path = tmp_path / "governance_invariants.sqlite"
    database_url = f"sqlite:///{database_path}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            SourceWorkORM(
                source_domain="tafsir",
                work_slug="ibn-kathir-en",
                source_id="tafsir:ibn-kathir-en",
                display_name="Tafsir Ibn Kathir (English)",
                citation_label="Tafsir Ibn Kathir",
                author_name="Ibn Kathir",
                language_code="en",
                source_kind="commentary",
                upstream_provider="quran_foundation",
                upstream_resource_id=169,
                enabled=False,
                approved_for_answering=False,
                default_for_explain=True,
                supports_quran_composition=True,
                priority_rank=10,
                policy_note="Broken overlay state.",
                metadata_json={},
            )
        )
        session.commit()

    issues = run_source_governance_checks(database_url=database_url)
    codes = {issue.code for issue in issues}
    assert "default_requires_enabled_approved" in codes
    assert "composition_requires_enabled_approved" in codes
    fallback = get_default_tafsir_source_for_explain(database_url=database_url)
    assert fallback is not None
    assert fallback.source_id == 'tafsir:tafheem-al-quran-en'
