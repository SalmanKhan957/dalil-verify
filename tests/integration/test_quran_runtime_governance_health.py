import httpx
import pytest

from apps.public_api.main import app as public_app
from services.quran_runtime import bootstrap as runtime_bootstrap


@pytest.mark.anyio
async def test_public_health_reports_quran_runtime_governance_details(monkeypatch):
    monkeypatch.setenv("DALIL_QURAN_TEXT_SOURCE_ID", "quran:tanzil-simple")
    monkeypatch.setenv("DALIL_QURAN_TRANSLATION_SOURCE_ID", "quran:towards-understanding-en")
    runtime_bootstrap.refresh_runtime_state()

    transport = httpx.ASGITransport(app=public_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_governance"]["checked"] is True
    assert payload["source_governance"]["quran_repository"]["checked"] is True
    assert payload["source_governance"]["quran_repository"]["quran_work_source_id"] == "quran:tanzil-simple"
    assert payload["source_governance"]["quran_repository"]["translation_work_source_id"] == "quran:towards-understanding-en"
