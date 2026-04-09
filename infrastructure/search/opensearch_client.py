from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class OpenSearchClient:
    base_url: str | None = None
    username: str | None = None
    password: str | None = None
    verify_ssl: bool = True
    timeout_seconds: float = 10.0

    @classmethod
    def from_environment(cls) -> 'OpenSearchClient':
        verify_value = str(os.getenv('OPENSEARCH_VERIFY_SSL', 'true')).strip().casefold()
        return cls(
            base_url=(os.getenv('OPENSEARCH_URL') or '').strip() or None,
            username=(os.getenv('OPENSEARCH_USERNAME') or '').strip() or None,
            password=(os.getenv('OPENSEARCH_PASSWORD') or '').strip() or None,
            verify_ssl=verify_value not in {'0', 'false', 'no'},
            timeout_seconds=float(os.getenv('OPENSEARCH_TIMEOUT_SECONDS', '10') or 10),
        )

    @property
    def is_enabled(self) -> bool:
        return bool(self.base_url)

    def search(self, *, index: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._request('POST', f'/{index}/_search', json_body=body)

    def index_exists(self, *, index: str) -> bool:
        if not self.is_enabled:
            return False
        response = self._request('HEAD', f'/{index}', allow_404=True)
        return bool(response.get('status_code') == 200)

    def create_index(self, *, index: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._request('PUT', f'/{index}', json_body=body)

    def bulk_index(self, *, index: str, documents: list[dict[str, Any]], id_field: str = 'canonical_ref') -> dict[str, Any]:
        lines: list[str] = []
        for document in documents:
            document_id = str(document.get(id_field) or '')
            action = {'index': {'_index': index}}
            if document_id:
                action['index']['_id'] = document_id
            lines.append(json.dumps(action, ensure_ascii=False))
            lines.append(json.dumps(document, ensure_ascii=False))
        payload = '\n'.join(lines) + ('\n' if lines else '')
        return self._request(
            'POST',
            '/_bulk',
            content=payload,
            headers={'Content-Type': 'application/x-ndjson'},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        content: str | None = None,
        headers: dict[str, str] | None = None,
        allow_404: bool = False,
    ) -> dict[str, Any]:
        if not self.is_enabled:
            raise RuntimeError('OpenSearch is not configured; set OPENSEARCH_URL to enable this path.')
        auth = (self.username, self.password) if self.username or self.password else None
        with httpx.Client(base_url=self.base_url, auth=auth, verify=self.verify_ssl, timeout=self.timeout_seconds) as client:
            response = client.request(method, path, json=json_body, content=content, headers=headers)
        if allow_404 and response.status_code == 404:
            return {'status_code': 404}
        response.raise_for_status()
        if not response.content:
            return {'status_code': response.status_code}
        return response.json()
