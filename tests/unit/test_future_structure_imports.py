from domains.ask.dispatcher import dispatch_ask_query
from domains.answer_engine.response_builder import build_explain_answer_payload
from domains.quran import fetch_quran_span, load_quran_metadata, resolve_quran_reference, verify_quran_text
from domains.tafsir.service import TafsirService
from domains.source_registry.registry import get_source_record
from infrastructure.clients.quran_foundation import QuranFoundationContentClient, TafsirChapterNotFoundError


def test_future_structure_imports_resolve() -> None:
    assert callable(dispatch_ask_query)
    assert callable(build_explain_answer_payload)
    assert callable(resolve_quran_reference)
    assert callable(load_quran_metadata)
    assert callable(fetch_quran_span)
    assert callable(verify_quran_text)
    assert TafsirService is not None
    assert callable(get_source_record)
    assert QuranFoundationContentClient is not None
    assert TafsirChapterNotFoundError is not None
