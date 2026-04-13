import pytest

pytest.importorskip('sqlalchemy')

from fastapi.testclient import TestClient

from apps.public_api.main import app


def test_hadith_followup_thread_retains_hadith_scope() -> None:
    with TestClient(app) as client:
        first = client.post('/ask', headers={'x-conversation-id': 'conv-hadith-hardening'}, json={'query': 'Explain Bukhari 7'})
        assert first.status_code == 200
        second = client.post('/ask', headers={'x-conversation-id': 'conv-hadith-hardening'}, json={'query': 'Summarize this hadith'})
        assert second.status_code == 200
        body2 = (second.json().get('result') or second.json())
        assert body2.get('route_type') == 'anchored_followup_hadith'
        assert (body2.get('composition') or {}).get('active_followup_action', {}).get('action_type') == 'summarize_hadith'
