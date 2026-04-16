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

from infrastructure.cache.keys import anchor_session_key as redis_anchor_session_key
from infrastructure.cache.keys import anchor_turn_key as redis_anchor_turn_key
from infrastructure.cache.redis_client import RedisUnavailableError, get_anchor_store_redis_client
from infrastructure.config.settings import settings


@dataclass(slots=True)
class StoredAnchorSet:
    session_key: str
    turn_id: str
    anchor_refs: list[str] = field(default_factory=list)
    anchors: list[dict[str, Any]] = field(default_factory=list)
    session_state_payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    backend: str = 'memory'


_LOCK = threading.RLock()
_BY_SESSION: dict[str, StoredAnchorSet] = {}
_BY_TURN: dict[str, StoredAnchorSet] = {}
_SQLITE_READY = False


ALLOWED_BACKENDS = {'memory', 'sqlite', 'redis'}


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
    seen_refs: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        canonical_ref = _clean_string(item.get('canonical_ref'))
        if canonical_ref is None or canonical_ref in seen_refs:
            continue
        seen_refs.add(canonical_ref)
        payload = dict(item)
        payload['canonical_ref'] = canonical_ref
        payloads.append(payload)
    return payloads


def _normalize_session_state_payload(raw: object) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, dict) else {}


def _anchor_store_backend() -> str:
    backend = str(getattr(settings, 'anchor_store_backend', 'memory') or 'memory').strip().lower()
    return backend if backend in ALLOWED_BACKENDS else 'memory'


def _anchor_store_ttl_seconds() -> int:
    ttl = int(getattr(settings, 'anchor_store_ttl_seconds', 21600) or 21600)
    return ttl if ttl > 0 else 21600


def _anchor_store_namespace() -> str:
    namespace = str(getattr(settings, 'anchor_store_namespace', 'dalil:conversation') or 'dalil:conversation').strip()
    return namespace or 'dalil:conversation'


def _expires_at_from_now() -> float:
    return time.time() + float(_anchor_store_ttl_seconds())


def _record_is_expired(record: StoredAnchorSet | None, *, now: float | None = None) -> bool:
    if record is None:
        return True
    if record.expires_at is None:
        return False
    current = time.time() if now is None else now
    return record.expires_at <= current


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
                    session_state_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                '''
            )
            connection.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_anchor_sets_turn_id ON anchor_sets(turn_id)')
            columns = {row['name'] for row in connection.execute('PRAGMA table_info(anchor_sets)')}
            if 'session_state_json' not in columns:
                connection.execute("ALTER TABLE anchor_sets ADD COLUMN session_state_json TEXT NOT NULL DEFAULT '{}' ")
            if 'expires_at' not in columns:
                connection.execute('ALTER TABLE anchor_sets ADD COLUMN expires_at REAL')
                default_expires = _expires_at_from_now()
                connection.execute('UPDATE anchor_sets SET expires_at = COALESCE(expires_at, created_at + ?, ?)', (_anchor_store_ttl_seconds(), default_expires))
            connection.execute('DELETE FROM anchor_sets WHERE expires_at IS NOT NULL AND expires_at <= ?', (time.time(),))
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
    try:
        session_state_payload = json.loads(row['session_state_json'])
    except Exception:
        session_state_payload = {}
    expires_at = row['expires_at'] if 'expires_at' in row.keys() else None
    record = StoredAnchorSet(
        session_key=str(row['session_key']),
        turn_id=str(row['turn_id']),
        anchor_refs=_normalize_anchor_refs(anchor_refs),
        anchors=_normalize_anchor_payloads(anchors),
        session_state_payload=_normalize_session_state_payload(session_state_payload),
        created_at=float(row['created_at'] or time.time()),
        expires_at=float(expires_at) if expires_at is not None else None,
        backend='sqlite',
    )
    if _record_is_expired(record):
        return None
    return record


def _record_to_json_payload(record: StoredAnchorSet) -> str:
    return json.dumps(
        {
            'session_key': record.session_key,
            'turn_id': record.turn_id,
            'anchor_refs': list(record.anchor_refs),
            'anchors': list(record.anchors),
            'session_state_payload': dict(record.session_state_payload),
            'created_at': record.created_at,
            'expires_at': record.expires_at,
            'backend': record.backend,
        },
        ensure_ascii=False,
    )


def _record_from_json_payload(raw: str | None, *, backend: str) -> StoredAnchorSet | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    record = StoredAnchorSet(
        session_key=str(payload.get('session_key') or '').strip(),
        turn_id=str(payload.get('turn_id') or '').strip(),
        anchor_refs=_normalize_anchor_refs(payload.get('anchor_refs')),
        anchors=_normalize_anchor_payloads(payload.get('anchors')),
        session_state_payload=_normalize_session_state_payload(payload.get('session_state_payload')),
        created_at=float(payload.get('created_at') or time.time()),
        expires_at=float(payload['expires_at']) if payload.get('expires_at') is not None else None,
        backend=backend,
    )
    if not record.session_key or not record.turn_id or _record_is_expired(record):
        return None
    return record


def _build_record(*, session_key: str, anchors: list[dict[str, Any]], session_state_payload: dict[str, Any] | None = None, backend: str) -> StoredAnchorSet | None:
    normalized_payloads = _normalize_anchor_payloads(anchors)
    normalized_refs = [item['canonical_ref'] for item in normalized_payloads]
    if not normalized_refs:
        return None
    return StoredAnchorSet(
        session_key=session_key,
        turn_id=uuid.uuid4().hex,
        anchor_refs=normalized_refs,
        anchors=normalized_payloads,
        session_state_payload=_normalize_session_state_payload(session_state_payload),
        expires_at=_expires_at_from_now(),
        backend=backend,
    )


def _delete_memory_record(record: StoredAnchorSet | None) -> None:
    if record is None:
        return
    with _LOCK:
        current = _BY_SESSION.get(record.session_key)
        if current is not None and current.turn_id == record.turn_id:
            _BY_SESSION.pop(record.session_key, None)
        _BY_TURN.pop(record.turn_id, None)


def _save_response_anchors_memory(*, session_key: str, anchors: list[dict[str, Any]], session_state_payload: dict[str, Any] | None = None) -> StoredAnchorSet | None:
    record = _build_record(session_key=session_key, anchors=anchors, session_state_payload=session_state_payload, backend='memory')
    if record is None:
        return None
    with _LOCK:
        _BY_SESSION[session_key] = record
        _BY_TURN[record.turn_id] = record
    return record


def _save_response_anchors_sqlite(*, session_key: str, anchors: list[dict[str, Any]], session_state_payload: dict[str, Any] | None = None) -> StoredAnchorSet | None:
    record = _build_record(session_key=session_key, anchors=anchors, session_state_payload=session_state_payload, backend='sqlite')
    if record is None:
        return None
    _ensure_sqlite_schema()
    with _sqlite_connection() as connection:
        connection.execute(
            '''
            INSERT INTO anchor_sets(session_key, turn_id, anchor_refs_json, anchors_json, session_state_json, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_key) DO UPDATE SET
                turn_id = excluded.turn_id,
                anchor_refs_json = excluded.anchor_refs_json,
                anchors_json = excluded.anchors_json,
                session_state_json = excluded.session_state_json,
                created_at = excluded.created_at,
                expires_at = excluded.expires_at
            ''',
            (
                record.session_key,
                record.turn_id,
                json.dumps(record.anchor_refs, ensure_ascii=False),
                json.dumps(record.anchors, ensure_ascii=False),
                json.dumps(record.session_state_payload, ensure_ascii=False),
                record.created_at,
                record.expires_at,
            ),
        )
        connection.execute('DELETE FROM anchor_sets WHERE expires_at <= ?', (time.time(),))
        connection.commit()
    return record


def _save_response_anchors_redis(*, session_key: str, anchors: list[dict[str, Any]], session_state_payload: dict[str, Any] | None = None) -> StoredAnchorSet | None:
    record = _build_record(session_key=session_key, anchors=anchors, session_state_payload=session_state_payload, backend='redis')
    if record is None:
        return None
    client = get_anchor_store_redis_client()
    namespace = _anchor_store_namespace()
    ttl = _anchor_store_ttl_seconds()
    payload = _record_to_json_payload(record)
    client.set(redis_anchor_session_key(namespace=namespace, session_key=record.session_key), payload, ex=ttl)
    client.set(redis_anchor_turn_key(namespace=namespace, turn_id=record.turn_id), payload, ex=ttl)
    return record


def _get_anchors_for_parent_turn_memory(parent_turn_id: str | None) -> StoredAnchorSet | None:
    cleaned = _clean_string(parent_turn_id)
    if cleaned is None:
        return None
    with _LOCK:
        record = _BY_TURN.get(cleaned)
    if _record_is_expired(record):
        _delete_memory_record(record)
        return None
    return record


def _get_anchors_for_parent_turn_sqlite(parent_turn_id: str | None) -> StoredAnchorSet | None:
    cleaned = _clean_string(parent_turn_id)
    if cleaned is None:
        return None
    _ensure_sqlite_schema()
    with _sqlite_connection() as connection:
        row = connection.execute(
            'SELECT session_key, turn_id, anchor_refs_json, anchors_json, session_state_json, created_at, expires_at FROM anchor_sets WHERE turn_id = ? AND expires_at > ?',
            (cleaned, time.time()),
        ).fetchone()
    return _row_to_record(row)


def _get_anchors_for_parent_turn_redis(parent_turn_id: str | None) -> StoredAnchorSet | None:
    cleaned = _clean_string(parent_turn_id)
    if cleaned is None:
        return None
    client = get_anchor_store_redis_client()
    payload = client.get(redis_anchor_turn_key(namespace=_anchor_store_namespace(), turn_id=cleaned))
    return _record_from_json_payload(payload, backend='redis')


def _get_latest_anchors_for_session_memory(session_key: str | None) -> StoredAnchorSet | None:
    if not session_key:
        return None
    with _LOCK:
        record = _BY_SESSION.get(session_key)
    if _record_is_expired(record):
        _delete_memory_record(record)
        return None
    return record


def _get_latest_anchors_for_session_sqlite(session_key: str | None) -> StoredAnchorSet | None:
    if not session_key:
        return None
    _ensure_sqlite_schema()
    with _sqlite_connection() as connection:
        row = connection.execute(
            'SELECT session_key, turn_id, anchor_refs_json, anchors_json, session_state_json, created_at, expires_at FROM anchor_sets WHERE session_key = ? AND expires_at > ?',
            (session_key, time.time()),
        ).fetchone()
    return _row_to_record(row)


def _get_latest_anchors_for_session_redis(session_key: str | None) -> StoredAnchorSet | None:
    if not session_key:
        return None
    client = get_anchor_store_redis_client()
    payload = client.get(redis_anchor_session_key(namespace=_anchor_store_namespace(), session_key=session_key))
    return _record_from_json_payload(payload, backend='redis')


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


def save_response_anchors(*, session_key: str | None, anchors: list[dict[str, Any]], session_state_payload: dict[str, Any] | None = None) -> StoredAnchorSet | None:
    if not session_key:
        return None
    backend = _anchor_store_backend()
    if backend == 'sqlite':
        return _save_response_anchors_sqlite(session_key=session_key, anchors=anchors, session_state_payload=session_state_payload)
    if backend == 'redis':
        try:
            return _save_response_anchors_redis(session_key=session_key, anchors=anchors, session_state_payload=session_state_payload)
        except (RedisUnavailableError, Exception):
            return _save_response_anchors_sqlite(session_key=session_key, anchors=anchors, session_state_payload=session_state_payload)
    return _save_response_anchors_memory(session_key=session_key, anchors=anchors, session_state_payload=session_state_payload)


def get_anchors_for_parent_turn(parent_turn_id: str | None) -> StoredAnchorSet | None:
    backend = _anchor_store_backend()
    if backend == 'sqlite':
        return _get_anchors_for_parent_turn_sqlite(parent_turn_id)
    if backend == 'redis':
        try:
            return _get_anchors_for_parent_turn_redis(parent_turn_id)
        except (RedisUnavailableError, Exception):
            return _get_anchors_for_parent_turn_sqlite(parent_turn_id)
    return _get_anchors_for_parent_turn_memory(parent_turn_id)


def get_latest_anchors_for_session(session_key: str | None) -> StoredAnchorSet | None:
    backend = _anchor_store_backend()
    if backend == 'sqlite':
        return _get_latest_anchors_for_session_sqlite(session_key)
    if backend == 'redis':
        try:
            return _get_latest_anchors_for_session_redis(session_key)
        except (RedisUnavailableError, Exception):
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
            if record.session_state_payload:
                context['_hydrated_session_state'] = dict(record.session_state_payload)
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
        if record.session_state_payload:
            context['_hydrated_session_state'] = dict(record.session_state_payload)
        context['_anchor_resolution_mode'] = 'conversation_hydrated' if explicit_conversation_id is not None else 'implicit_session_hydrated'
        context['_anchor_session_key'] = record.session_key
        return context

    context['_anchor_resolution_mode'] = 'none'
    return context
