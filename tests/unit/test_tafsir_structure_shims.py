from domains.tafsir.service import TafsirService as DomainTafsirService
from domains.tafsir.repositories.tafsir_repository import SqlAlchemyTafsirRepository as DomainTafsirRepository
from services.tafsir.repository import SqlAlchemyTafsirRepository as ServiceTafsirRepository
from services.tafsir.service import TafsirService as ServiceTafsirService


def test_tafsir_repository_service_shims_resolve() -> None:
    assert DomainTafsirRepository is ServiceTafsirRepository
    assert DomainTafsirService is not None
    assert ServiceTafsirService is not None
