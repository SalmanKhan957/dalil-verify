from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from infrastructure.config.settings import settings
from domains.answer_engine.renderer_prompts import DALIL_RENDERER_SYSTEM_PROMPT, build_renderer_user_prompt


def _responses_api_payload(*, composition: dict[str, Any], deterministic_answer_text: str | None) -> dict[str, Any]:
    schema = {
        'name': 'dalil_renderer_response',
        'schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'answer_text': {'type': 'string'},
                'followup_suggestions': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 4},
                'style_applied': {'type': 'string'},
            },
            'required': ['answer_text', 'followup_suggestions', 'style_applied'],
        },
        'strict': True,
    }
    return {
        'model': settings.renderer_model,
        'input': [
            {'role': 'system', 'content': [{'type': 'input_text', 'text': DALIL_RENDERER_SYSTEM_PROMPT}]},
            {'role': 'user', 'content': [{'type': 'input_text', 'text': build_renderer_user_prompt(composition=composition, deterministic_answer_text=deterministic_answer_text)}]},
        ],
        'max_output_tokens': settings.renderer_max_output_tokens,
        'text': {'format': {'type': 'json_schema', **schema}},
    }


def _extract_text_blob(payload: dict[str, Any]) -> str:
    if isinstance(payload.get('output_text'), str) and payload.get('output_text').strip():
        return payload['output_text']
    for item in list(payload.get('output') or []):
        for content in list(item.get('content') or []):
            text = content.get('text')
            if isinstance(text, str) and text.strip():
                return text
    return ''


def render_with_openai(*, composition: dict[str, Any], deterministic_answer_text: str | None) -> dict[str, Any] | None:
    if not settings.openai_api_key.strip():
        return None
    req = urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(_responses_api_payload(composition=composition, deterministic_answer_text=deterministic_answer_text)).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {settings.openai_api_key}'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.renderer_timeout_seconds) as response:
            raw = response.read().decode('utf-8')
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return None
    try:
        response_payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    text_blob = _extract_text_blob(response_payload)
    if not text_blob:
        return None
    try:
        rendered = json.loads(text_blob)
    except json.JSONDecodeError:
        return None
    answer_text = str(rendered.get('answer_text') or '').strip()
    followups = [str(item).strip() for item in list(rendered.get('followup_suggestions') or []) if str(item).strip()]
    style_applied = str(rendered.get('style_applied') or '').strip()
    if not answer_text:
        return None
    return {'answer_text': answer_text, 'followup_suggestions': followups[:4], 'style_applied': style_applied or 'openai_renderer'}
