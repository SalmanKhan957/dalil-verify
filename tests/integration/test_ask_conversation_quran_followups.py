import pytest

pytest.importorskip('sqlalchemy')

from fastapi.testclient import TestClient

from apps.public_api.main import app


def test_quran_followup_thread_retains_anchor_and_source_focus() -> None:
    with TestClient(app) as client:
        first = client.post('/ask', headers={'x-conversation-id': 'conv-quran-hardening'}, json={'query': 'Explain 2:255-256'})
        assert first.status_code == 200
        second = client.post('/ask', headers={'x-conversation-id': 'conv-quran-hardening'}, json={'query': 'What does Tafheem say?'})
        assert second.status_code == 200
        body2 = (second.json().get('result') or second.json())
        assert body2.get('route_type') == 'anchored_followup_tafsir'
        assert (body2.get('composition') or {}).get('active_followup_action', {}).get('target_source_id') == 'tafsir:tafheem-al-quran-en'
