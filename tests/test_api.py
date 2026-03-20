from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app


def _noop_log(*args, **kwargs):
    return None


def test_health_endpoint(monkeypatch):
    monkeypatch.setattr("apps.api.main.append_jsonl_log", _noop_log)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == "dalil-verify-api"
    assert data["quran_rows_loaded"] > 0
    assert data["quran_passage_rows_loaded"] > 0


def test_verify_quran_single_ayah_prefers_ayah_lane(monkeypatch):
    monkeypatch.setattr("apps.api.main.append_jsonl_log", _noop_log)

    with TestClient(app) as client:
        response = client.post("/verify/quran", json={"text": "فان مع العسر يسرا"})

    assert response.status_code == 200
    data = response.json()

    assert data["preferred_lane"] == "ayah"
    assert data["best_match"]["citation"] == "Quran 94:5"
    assert data["match_status"] == "Exact match found"
    assert isinstance(data["also_related"], list)


def test_verify_quran_multi_ayah_prefers_passage_lane(monkeypatch):
    monkeypatch.setattr("apps.api.main.append_jsonl_log", _noop_log)

    with TestClient(app) as client:
        response = client.post(
            "/verify/quran",
            json={"text": "فويل للمصلين الذين هم عن صلاتهم ساهون"},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["preferred_lane"] == "passage"
    assert data["best_match"]["citation"] == "Quran 107:4-5"


def test_verify_quran_ask_like_routes_to_ask_engine(monkeypatch):
    monkeypatch.setattr("apps.api.main.append_jsonl_log", _noop_log)

    with TestClient(app) as client:
        response = client.post(
            "/verify/quran",
            json={"text": "What is the punishment of zina?"},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["preferred_lane"] == "ask_engine"
    assert data["best_match"] is None
    assert data["match_status"] == "Cannot assess"


def test_verify_quran_too_short_returns_cannot_assess(monkeypatch):
    monkeypatch.setattr("apps.api.main.append_jsonl_log", _noop_log)

    with TestClient(app) as client:
        response = client.post("/verify/quran", json={"text": "رحمة"})

    assert response.status_code == 200
    data = response.json()

    assert data["preferred_lane"] == "none"
    assert data["best_match"] is None
    assert data["match_status"] == "Cannot assess"


def test_verify_quran_debug_mode(monkeypatch):
    monkeypatch.setattr("apps.api.main.append_jsonl_log", _noop_log)

    with TestClient(app) as client:
        response = client.post(
            "/verify/quran?debug=true",
            json={"text": "فان مع العسر يسرا"},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["preferred_lane"] == "ayah"
    assert data["debug"] is not None
    assert "ayah_result" in data["debug"]
    assert "passage_result" in data["debug"]


def test_verify_quran_empty_input_rejected(monkeypatch):
    monkeypatch.setattr("apps.api.main.append_jsonl_log", _noop_log)

    with TestClient(app) as client:
        response = client.post("/verify/quran", json={"text": "   "})

    assert response.status_code == 400
    data = response.json()

    assert data["detail"] == "Input text cannot be empty."

def test_verify_quran_long_same_surah_span_prefers_dynamic_passage(monkeypatch):
    monkeypatch.setattr("apps.api.main.append_jsonl_log", _noop_log)

    from apps.api import main as main_module

    with TestClient(app) as client:
        query = " ".join(
            row["text_display"]
            for row in main_module.QURAN_ROWS
            if row["surah_no"] == 46 and 9 <= row["ayah_no"] <= 13
        )
        response = client.post("/verify/quran?debug=true", json={"text": query})

    assert response.status_code == 200
    data = response.json()

    assert data["preferred_lane"] == "passage"
    assert data["best_match"]["citation"] == "Quran 46:9-13"
    assert data["best_match"]["window_size"] == 5
    assert data["best_match"]["retrieval_engine"] == "surah_span_exact"
    assert not any(item.get("citation") == "Quran 5:110" for item in data["also_related"])
    assert data["debug"]["shortlist"]["dynamic_passage"]["engine"] == "surah_span_exact"
