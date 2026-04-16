from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from infrastructure.config.settings import settings

_QUERY_NORMALIZER_SYSTEM_PROMPT = """You are DALIL's query normalizer.
Your job is ONLY to clean malformed user input before deterministic routing.

Allowed operations:
- restore missing spaces
- fix obvious spelling mistakes
- normalize common transliteration variants
- normalize honorific noise like ﷺ if needed
- preserve explicit references, numbers, source names, and topic intent

Forbidden operations:
- do not answer the question
- do not choose a source or route
- do not broaden or narrow the user's intent
- do not add religious content
- do not invent citations or references
- do not turn an ambiguous query into a more specific one

Return the safest cleaned query for routing. If unsure, stay very close to the original meaning.
"""


def _responses_api_payload(*, raw_query: str, deterministic_baseline: str) -> dict[str, Any]:
    schema = {
        'name': 'dalil_query_normalization',
        'description': 'Constrained query cleanup for DALIL pre-classifier routing.',
        'schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'normalized_query': {'type': 'string'},
                'confidence': {'type': 'number'},
                'normalization_type': {
                    'type': 'string',
                    'enum': ['identity', 'spacing', 'spelling', 'transliteration', 'canonicalization', 'mixed'],
                },
                'did_change_meaning': {'type': 'boolean'},
                'notes': {'type': 'string'},
            },
            'required': ['normalized_query', 'confidence', 'normalization_type', 'did_change_meaning', 'notes'],
        },
        'strict': True,
    }
    return {
        'model': settings.query_normalization_model,
        'store': False,
        'input': [
            {'role': 'system', 'content': [{'type': 'input_text', 'text': _QUERY_NORMALIZER_SYSTEM_PROMPT}]},
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': (
                            'Normalize this DALIL user query for routing only.\n\n'
                            f'Raw query: {raw_query!r}\n'
                            f'Deterministic baseline: {deterministic_baseline!r}\n\n'
                            'Return only the safest cleaned query. Preserve meaning, source mentions, and numbers.'
                        ),
                    }
                ],
            },
        ],
        'max_output_tokens': settings.query_normalization_max_output_tokens,
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


def normalize_with_openai(*, raw_query: str, deterministic_baseline: str) -> dict[str, Any]:
    model = settings.query_normalization_model
    if not settings.openai_api_key.strip():
        return {
            'ok': False,
            'error_class': 'missing_api_key',
            'fallback_reason': 'hosted_missing_api_key',
            'model': model,
        }
    req = urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(_responses_api_payload(raw_query=raw_query, deterministic_baseline=deterministic_baseline)).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {settings.openai_api_key}'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.query_normalization_timeout_seconds) as response:
            raw = response.read().decode('utf-8')
    except urllib.error.HTTPError:
        return {
            'ok': False,
            'error_class': 'http_error',
            'fallback_reason': 'hosted_http_error',
            'model': model,
        }
    except urllib.error.URLError:
        return {
            'ok': False,
            'error_class': 'url_error',
            'fallback_reason': 'hosted_transport_error',
            'model': model,
        }
    except TimeoutError:
        return {
            'ok': False,
            'error_class': 'timeout',
            'fallback_reason': 'hosted_timeout',
            'model': model,
        }
    except ValueError:
        return {
            'ok': False,
            'error_class': 'value_error',
            'fallback_reason': 'hosted_request_error',
            'model': model,
        }
    try:
        response_payload = json.loads(raw)
    except json.JSONDecodeError:
        return {
            'ok': False,
            'error_class': 'response_json_decode_error',
            'fallback_reason': 'hosted_invalid_response_json',
            'model': model,
        }
    text_blob = _extract_text_blob(response_payload)
    if not text_blob:
        return {
            'ok': False,
            'error_class': 'empty_output_text',
            'fallback_reason': 'hosted_empty_output_text',
            'model': model,
        }
    try:
        normalized = json.loads(text_blob)
    except json.JSONDecodeError:
        return {
            'ok': False,
            'error_class': 'structured_output_json_decode_error',
            'fallback_reason': 'hosted_invalid_structured_output',
            'model': model,
        }
    cleaned_query = str(normalized.get('normalized_query') or '').strip()
    if not cleaned_query:
        return {
            'ok': False,
            'error_class': 'empty_normalized_query',
            'fallback_reason': 'hosted_empty_candidate',
            'model': model,
        }
    return {
        'ok': True,
        'normalized_query': cleaned_query,
        'confidence': float(normalized.get('confidence') or 0.0),
        'normalization_type': str(normalized.get('normalization_type') or 'mixed').strip() or 'mixed',
        'did_change_meaning': bool(normalized.get('did_change_meaning')),
        'notes': str(normalized.get('notes') or '').strip(),
        'model': model,
    }
