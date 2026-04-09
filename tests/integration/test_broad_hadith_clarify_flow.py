from __future__ import annotations

import httpx
import pytest

from apps.ask_api.main import app


@pytest.mark.anyio
async def test_ask_route_returns_clarify_for_broad_hadith_self_improvement_query() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post('/ask', json={'query': 'How can I improve myself according to hadith?'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['route_type'] == 'unsupported_for_now'
    assert payload['answer_mode'] == 'clarify'
    assert payload['ok'] is True
    assert payload['error'] is None
    assert 'clarification_required' in payload['warnings']
    assert 'hadith guidance' in (payload['answer_text'] or '').lower()
