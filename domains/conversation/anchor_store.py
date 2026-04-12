from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Request

from infrastructure.config.settings import settings


@dataclass(slots=True)
class StoredAnchorSet:
    session_key: str
    turn_id: str
    anchor_refs: list[str] = field(default_factory=list)
    anchors: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


_LOCK = threading.RLock()
_BY_SESSION: dict[str, StoredAnchorSet] = {}
_BY_TURN: dict[str, StoredAnchorSet] = {}
_SQLITE_READY = False


def _clean_string(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _normalize_anchor_refs(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    refs: list[str] = []
    seen: set[str] = set()
    for item in raw:
        cleaned = _clean_string(item)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        refs.append(cleaned)
    return refs


def _normalize_anchor_payloads(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    payloads: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        canonical_ref = _clean_string(item.get('canonical_ref'))
        if canonical_ref is None:
            continue
        payload = dict(item)
        payload['canonical_ref'] = canonical_ref
        payloads.append(payload)
    return payloads


def _anchor_store_backend() -> str:
    backend = str(getattr(settings, 'anchor_store_backend', 'memory') or 'memory').strip().lower()
    return backend if backend in {'memory', 'sqlite'} else 'memory'


def _anchor_store_sqlite_path() -> Path:
    configured = getattr(settings, 'anchor_store_sqlite_path', None)
    path = Path(configured) if configured is not None else settings.repo_root / 'data' / 'runtime' / 'conversation' / 'anchor_store.sqlite3'
    if not path.is_absolute():
        path = settings.repo_root / path
    return path


def _sqlite_connection() -> sqlite3.Connection:
    path = _anchor_store_sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_sqlite_schema() -> None:
    global _SQLITE_READY
    if _SQLITE_READY:
        return
    with _LOCK:
        if _SQLITE_READY:
            return
        with _sqlite_connection() as connection:
            connection.execute('PRAGMA journal_mode=WAL;')
            connection.execute(
                '''
                CREATE TABLE IF NOT EXISTS anchor_sets (
                    session_key TEXT PRIMARY KEY,
                    turn_id TEXT NOT NULL UNIQUE,
                    anchor_refs_json TEXT NOT NULL,
                    anchors_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                '''
            )
            connection.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_anchor_sets_turn_id ON anchor_sets(turn_id)')
            connection.commit()
        _SQLITE_READY = True


def _row_to_record(row: sqlite3.Row | None) -> StoredAnchorSet | None:
    if row is None:
        return None
    try:
        anchor_refs = json.loads(row['anchor_refs_json'])
    except Exception:
        anchor_refs = []
    try:
        anchors = json.loads(row['anchors_json'])
    except Exception:
        anchors = []
    return StoredAnchorSet(
        session_key=str(row['session_key']),
        turn_id=str(row['turn_id']),
        anchor_refs=_normalize_anchor_refs(anchor_refs),
        anchors=_normalize_anchor_payloads(anchors),
        created_at=float(row['created_at'] or time.time()),
    )


def _save_response_anchors_memory(*, session_key: str, anchors: list[dict[str, Any]]) -> StoredAnchorSet | None:
    normalized_payloads = _normalize_anchor_payloads(anchors)
    normalized_refs = [item['canonical_ref'] for item in normalized_payloads]
    if not normalized_refs:
        return None
    record = StoredAnchorSet(
        session_key=session_key,
        turn_id=uuid.uuid4().hex,
        anchor_refs=normalized_refs,
        anchors=normalized_payloads,
    )
    with _LOCK:
        _BY_SESSION[session_key] = record
        _BY_TURN[record.turn_id] = record
    return record


def _save_response_anchors_sqlite(*, session_key: str, anchors: list[dict[str, Any]]) -> StoredAnchorSet | None:
    normalized_payloads = _normalize_anchor_payloads(anchors)
    normalized_refs = [item['canonical_ref'] for item in normalized_payloads]
    if not normalized_refs:
        return None
    record = StoredAnchorSet(
        session_key=session_key,
        turn_id=uuid.uuid4().hex,
        anchor_refs=normalized_refs,
        anchors=normalized_payloads,
    )
    _ensure_sqlite_schema()
    with _sqlite_connection() as connection:
        connection.execute(
            '''
            INSERT INTO anchor_sets(session_key, turn_id, anchor_refs_json, anchors_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_key) DO UPDATE SET
                turn_id = excluded.turn_id,
                anchor_refs_json = excluded.anchor_refs_json,
                anchors_json = excluded.anchors_json,
                created_at = excluded.created_at
            ''',
            (
                record.session_key,
                record.turn_id,
                json.dumps(record.anchor_refs, ensure_ascii=False),
                json.dumps(record.anchors, ensure_ascii=False),
                record.created_at,
            ),
        )
        connection.commit()
    return record


def _get_anchors_for_parent_turn_memory(parent_turn_id: str | None) -> StoredAnchorSet | None:
    cleaned = _clean_string(parent_turn_id)
    if cleaned is None:
        return None
    with _LOCK:
        return _BY_TURN.get(cleaned)


def _get_anchors_for_parent_turn_sqlite(parent_turn_id: str | None) -> StoredAnchorSet | None:
    cleaned = _clean_string(parent_turn_id)
    if cleaned is None:
        return None
    _ensure_sqlite_schema()
    with _sqlite_connection() as connection:
        row = connection.execute(
            'SELECT session_key, turn_id, anchor_refs_json, anchors_json, created_at FROM anchor_sets WHERE turn_id = ?',
            (cleaned,),
        ).fetchone()
    return _row_to_record(row)


def _get_latest_anchors_for_session_memory(session_key: str | None) -> StoredAnchorSet | None:
    if not session_key:
        return None
    with _LOCK:
        return _BY_SESSION.get(session_key)


def _get_latest_anchors_for_session_sqlite(session_key: str | None) -> StoredAnchorSet | None:
    if not session_key:
        return None
    _ensure_sqlite_schema()
    with _sqlite_connection() as connection:
        row = connection.execute(
            'SELECT session_key, turn_id, anchor_refs_json, anchors_json, created_at FROM anchor_sets WHERE session_key = ?',
            (session_key,),
        ).fetchone()
    return _row_to_record(row)


def derive_anchor_session_key(request: Request | None, request_context: dict[str, Any] | None = None) -> str | None:
    context = dict(request_context or {})
    explicit_conversation_id = _clean_string(context.get('conversation_id'))
    if explicit_conversation_id is not None:
        return f'conversation:{explicit_conversation_id}'

    if request is None:
        return None

    header_conversation_id = _clean_string(request.headers.get('x-conversation-id') or request.headers.get('x-dalil-conversation-id'))
    if header_conversation_id is not None:
        return f'conversation:{header_conversation_id}'

    client_host = getattr(getattr(request, 'client', None), 'host', None) or 'unknown'
    user_agent = request.headers.get('user-agent', '')
    forwarded_for = request.headers.get('x-forwarded-for', '')
    raw = f'{client_host}|{forwarded_for}|{user_agent}'
    digest = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:24]
    return f'implicit:{digest}'


def save_response_anchors(*, session_key: str | None, anchors: list[dict[str, Any]]) -> StoredAnchorSet | None:
    if not session_key:
        return None
    if _anchor_store_backend() == 'sqlite':
        return _save_response_anchors_sqlite(session_key=session_key, anchors=anchors)
    return _save_response_anchors_memory(session_key=session_key, anchors=anchors)


def get_anchors_for_parent_turn(parent_turn_id: str | None) -> StoredAnchorSet | None:
    if _anchor_store_backend() == 'sqlite':
        return _get_anchors_for_parent_turn_sqlite(parent_turn_id)
    return _get_anchors_for_parent_turn_memory(parent_turn_id)


def get_latest_anchors_for_session(session_key: str | None) -> StoredAnchorSet | None:
    if _anchor_store_backend() == 'sqlite':
        return _get_latest_anchors_for_session_sqlite(session_key)
    return _get_latest_anchors_for_session_memory(session_key)


def hydrate_request_context(
    *,
    request_context: dict[str, Any] | None,
    session_key: str | None,
    followup_like: bool,
) -> dict[str, Any]:
    context = dict(request_context or {})
    anchor_refs = _normalize_anchor_refs(context.get('anchor_refs'))
    if anchor_refs:
        context['anchor_refs'] = anchor_refs
        context['_anchor_resolution_mode'] = 'request_supplied'
        if session_key is not None:
            context['_anchor_session_key'] = session_key
        return context

    parent_turn_id = _clean_string(context.get('parent_turn_id'))
    if parent_turn_id is not None:
        record = get_anchors_for_parent_turn(parent_turn_id)
        if record is not None:
            context['anchor_refs'] = list(record.anchor_refs)
            context['_hydrated_anchors'] = list(record.anchors)
            context['_anchor_resolution_mode'] = 'parent_turn_hydrated'
            context['_anchor_session_key'] = record.session_key
            return context

    if session_key is not None:
        context['_anchor_session_key'] = session_key

    if not followup_like:
        context['_anchor_resolution_mode'] = 'none'
        return context

    record = get_latest_anchors_for_session(session_key)
    if record is not None:
        explicit_conversation_id = _clean_string(context.get('conversation_id'))
        context['anchor_refs'] = list(record.anchor_refs)
        context['_hydrated_anchors'] = list(record.anchors)
        context['_anchor_resolution_mode'] = 'conversation_hydrated' if explicit_conversation_id is not None else 'implicit_session_hydrated'
        context['_anchor_session_key'] = record.session_key
        return context

    context['_anchor_resolution_mode'] = 'none'
    return context
