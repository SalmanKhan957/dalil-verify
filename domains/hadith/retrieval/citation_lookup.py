from __future__ import annotations

from domains.hadith.contracts import HadithCitationLookupResult, HadithCitationReference
from domains.hadith.repositories.hadith_repository import SqlAlchemyHadithRepository
from infrastructure.db.session import get_session
from domains.source_registry.registry import get_source_record


class HadithCitationLookupService:
    """Deterministic Hadith citation lookup against canonical DALIL storage."""

    def __init__(self, *, database_url: str | None = None) -> None:
        self.database_url = database_url

    def lookup(self, citation: HadithCitationReference) -> HadithCitationLookupResult:
        source = get_source_record(citation.collection_source_id, database_url=self.database_url)
        if source is None or source.source_domain != 'hadith':
            return HadithCitationLookupResult(resolved=False, citation=citation, warnings=['hadith_collection_not_registered'], error='hadith_collection_not_registered')
        if not source.enabled:
            return HadithCitationLookupResult(resolved=False, citation=citation, warnings=['hadith_collection_not_enabled'], error='hadith_collection_not_enabled')

        with get_session(database_url=self.database_url) as session:
            repository = SqlAlchemyHadithRepository(session)
            collection = repository.get_collection_by_source_id(source.source_id)
            entry = repository.lookup_by_citation(citation=citation, source_id=source.source_id)
            if entry is None:
                return HadithCitationLookupResult(resolved=False, citation=citation, warnings=['hadith_citation_not_found'], error='hadith_citation_not_found')

        warnings: list[str] = []
        citation_quality = ((collection.metadata_json or {}).get('citation_quality') or {}) if collection is not None else {}
        if citation.reference_type.value == 'book_and_hadith' and citation_quality.get('book_hadith') == 'bootstrap_unverified':
            warnings.append('hadith_bootstrap_numbering_unverified')
        if citation.reference_type.value == 'book_chapter_and_hadith' and citation_quality.get('book_chapter_hadith') == 'bootstrap_unverified':
            warnings.append('hadith_bootstrap_numbering_unverified')
        return HadithCitationLookupResult(resolved=True, citation=citation, entry=entry, warnings=warnings, error=None)
