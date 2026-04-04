from domains.ask.dispatcher import dispatch_ask_query
from domains.answer_engine.response_builder import build_explain_answer_payload
from domains.quran.citations.resolver import resolve_quran_reference
from domains.tafsir.service import TafsirService
from domains.source_registry.registry import get_source_record


def test_future_structure_imports_resolve() -> None:
    assert callable(dispatch_ask_query)
    assert callable(build_explain_answer_payload)
    assert callable(resolve_quran_reference)
    assert TafsirService is not None
    assert callable(get_source_record)
