from domains.quran import resolve_quran_reference, verify_quran_text
from infrastructure.clients.quran_foundation import QuranFoundationTafsirAPI
from services.citation_resolver import parse_quran_reference
from services.quran_foundation_client import TafsirChapterNotFoundError
from services.quran_verifier import build_health_payload



def test_quran_domain_and_service_shims_resolve() -> None:
    assert callable(resolve_quran_reference)
    assert callable(verify_quran_text)
    assert callable(parse_quran_reference)
    assert callable(build_health_payload)
    assert QuranFoundationTafsirAPI is not None
    assert TafsirChapterNotFoundError is not None
