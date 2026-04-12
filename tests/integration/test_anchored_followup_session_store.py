from __future__ import annotations

from fastapi.testclient import TestClient

from apps.public_api.main import app


def test_anchored_followup_hydrates_from_conversation_session_store() -> None:
    with TestClient(app) as client:
        first = client.post(
            '/ask',
            headers={'x-conversation-id': 'conv-session-test'},
            json={'query': 'Tafsir of Surah Ikhlas'},
        )
        assert first.status_code == 200
        first_body = first.json()
        first_result = first_body.get('result') or first_body
        conversation = first_result.get('conversation') or {}
        assert conversation.get('followup_ready') is True

        second = client.post(
            '/ask',
            headers={'x-conversation-id': 'conv-session-test'},
            json={'query': 'What does Tafheem say?'},
        )
        assert second.status_code == 200
        second_body = second.json()
        second_result = second_body.get('result') or second_body
        assert second_result.get('route_type') == 'anchored_followup_tafsir'
        orchestration = second_result.get('orchestration') or {}
        request_context = orchestration.get('request_context') or {}
        assert request_context.get('anchor_resolution_mode') == 'conversation_hydrated'
