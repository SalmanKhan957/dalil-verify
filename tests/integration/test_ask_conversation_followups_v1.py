from fastapi.testclient import TestClient

from apps.public_api.main import app



def test_conversation_state_drives_simplify_and_repeat_followups() -> None:
    with TestClient(app) as client:
        first = client.post('/ask', headers={'x-conversation-id': 'conv-followup-v1'}, json={'query': 'Explain Surah Al-Ikhlas'})
        assert first.status_code == 200
        body1 = first.json()
        result1 = body1.get('result') or body1
        assert (result1.get('conversation') or {}).get('followup_ready') is True

        second = client.post('/ask', headers={'x-conversation-id': 'conv-followup-v1'}, json={'query': 'Say it more simply'})
        assert second.status_code == 200
        body2 = second.json()
        result2 = body2.get('result') or body2
        assert result2.get('route_type') == 'anchored_followup_tafsir'
        assert (result2.get('composition') or {}).get('active_followup_action', {}).get('action_type') == 'simplify'

        third = client.post('/ask', headers={'x-conversation-id': 'conv-followup-v1'}, json={'query': 'Show the exact wording again'})
        assert third.status_code == 200
        body3 = third.json()
        result3 = body3.get('result') or body3
        assert result3.get('route_type') == 'anchored_followup_quran'
        assert (result3.get('composition') or {}).get('active_followup_action', {}).get('action_type') == 'repeat_exact_text'
