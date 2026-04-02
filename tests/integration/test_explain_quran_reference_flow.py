from services.ask_workflows.explain_quran_reference import explain_quran_reference


def test_explain_explicit_reference_flow_returns_structured_quran_span():
    result = explain_quran_reference("Explain 94:5-6")

    assert result["ok"] is True
    assert result["intent"] == "explicit_quran_reference_explain"
    assert result["resolution"]["resolved"] is True
    assert result["resolution"]["canonical_source_id"] == "quran:94:5-6"
    assert result["quran_span"]["citation_string"] == "Quran 94:5-6"
    assert len(result["quran_span"]["ayah_rows"]) == 2
    assert result["quran_span"]["translation"]["translation_name"] == "Towards Understanding the Quran"


def test_explain_explicit_reference_flow_returns_structured_error_for_bad_reference():
    result = explain_quran_reference("Explain 115:1")

    assert result["ok"] is False
    assert result["intent"] == "explicit_quran_reference_explain"
    assert result["quran_span"] is None
    assert result["error"] == "invalid_surah_number"
