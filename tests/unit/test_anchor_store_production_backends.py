from __future__ import annotations

import time as pytime

from domains.conversation import anchor_store
from infrastructure.cache.redis_client import RedisUnavailableError, reset_redis_client
from infrastructure.config.settings import settings


class _FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.current = start

    def time(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


class _FakeRedis:
    def __init__(self) -> None:
        self._values: dict[str, tuple[str, float | None]] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        expires_at = pytime.time() + ex if ex is not None else None
        self._values[key] = (value, expires_at)

    def get(self, key: str) -> str | None:
        payload = self._values.get(key)
        if payload is None:
            return None
        value, expires_at = payload
        if expires_at is not None and expires_at <= pytime.time():
            self._values.pop(key, None)
            return None
        return value

    def close(self) -> None:
        return None


def test_memory_anchor_store_respects_ttl(monkeypatch) -> None:
    old_backend = settings.anchor_store_backend
    old_ttl = settings.anchor_store_ttl_seconds
    old_by_session = dict(anchor_store._BY_SESSION)
    old_by_turn = dict(anchor_store._BY_TURN)
    clock = _FakeClock()
    try:
        settings.anchor_store_backend = 'memory'
        settings.anchor_store_ttl_seconds = 5
        anchor_store._BY_SESSION.clear()
        anchor_store._BY_TURN.clear()
        monkeypatch.setattr(anchor_store.time, 'time', clock.time)

        saved = anchor_store.save_response_anchors(
            session_key='conversation:test-memory',
            anchors=[{'canonical_ref': 'quran:112:1-4', 'source_domain': 'quran'}],
        )
        assert saved is not None
        assert saved.expires_at == 1005.0

        clock.advance(6)
        assert anchor_store.get_latest_anchors_for_session('conversation:test-memory') is None
        assert anchor_store.get_anchors_for_parent_turn(saved.turn_id) is None
    finally:
        settings.anchor_store_backend = old_backend
        settings.anchor_store_ttl_seconds = old_ttl
        anchor_store._BY_SESSION.clear()
        anchor_store._BY_SESSION.update(old_by_session)
        anchor_store._BY_TURN.clear()
        anchor_store._BY_TURN.update(old_by_turn)


def test_sqlite_anchor_store_round_trip_with_ttl(tmp_path) -> None:
    old_backend = settings.anchor_store_backend
    old_path = settings.anchor_store_sqlite_path
    old_ttl = settings.anchor_store_ttl_seconds
    old_ready = anchor_store._SQLITE_READY
    try:
        settings.anchor_store_backend = 'sqlite'
        settings.anchor_store_sqlite_path = tmp_path / 'anchor_store.sqlite3'
        settings.anchor_store_ttl_seconds = 60
        anchor_store._SQLITE_READY = False

        saved = anchor_store.save_response_anchors(
            session_key='conversation:test-sqlite',
            anchors=[{'canonical_ref': 'hadith:sahih-al-bukhari-en:7', 'source_domain': 'hadith'}],
        )
        assert saved is not None
        latest = anchor_store.get_latest_anchors_for_session('conversation:test-sqlite')
        assert latest is not None
        assert latest.backend == 'sqlite'
        assert latest.expires_at is not None
        assert latest.expires_at > latest.created_at
    finally:
        settings.anchor_store_backend = old_backend
        settings.anchor_store_sqlite_path = old_path
        settings.anchor_store_ttl_seconds = old_ttl
        anchor_store._SQLITE_READY = old_ready


def test_redis_anchor_store_round_trip_with_fake_client(monkeypatch) -> None:
    old_backend = settings.anchor_store_backend
    old_ttl = settings.anchor_store_ttl_seconds
    old_namespace = settings.anchor_store_namespace
    reset_redis_client()
    try:
        settings.anchor_store_backend = 'redis'
        settings.anchor_store_ttl_seconds = 120
        settings.anchor_store_namespace = 'dalil:test'
        monkeypatch.setattr(anchor_store, 'get_anchor_store_redis_client', lambda: _FakeRedis())

        fake = _FakeRedis()
        monkeypatch.setattr(anchor_store, 'get_anchor_store_redis_client', lambda: fake)

        saved = anchor_store.save_response_anchors(
            session_key='conversation:test-redis',
            anchors=[{'canonical_ref': 'quran:2:255', 'source_domain': 'quran'}],
            session_state_payload={'scope': {'quran_ref': 'quran:2:255'}},
        )
        assert saved is not None
        latest = anchor_store.get_latest_anchors_for_session('conversation:test-redis')
        assert latest is not None
        assert latest.backend == 'redis'
        by_turn = anchor_store.get_anchors_for_parent_turn(saved.turn_id)
        assert by_turn is not None
        assert by_turn.anchor_refs == ['quran:2:255']
        assert latest.session_state_payload['scope']['quran_ref'] == 'quran:2:255'
    finally:
        settings.anchor_store_backend = old_backend
        settings.anchor_store_ttl_seconds = old_ttl
        settings.anchor_store_namespace = old_namespace
        reset_redis_client()


def test_redis_backend_falls_back_to_sqlite_when_unavailable(tmp_path, monkeypatch) -> None:
    old_backend = settings.anchor_store_backend
    old_path = settings.anchor_store_sqlite_path
    old_ready = anchor_store._SQLITE_READY
    try:
        settings.anchor_store_backend = 'redis'
        settings.anchor_store_sqlite_path = tmp_path / 'anchor_store.sqlite3'
        anchor_store._SQLITE_READY = False
        monkeypatch.setattr(anchor_store, 'get_anchor_store_redis_client', lambda: (_ for _ in ()).throw(RedisUnavailableError('no redis')))

        saved = anchor_store.save_response_anchors(
            session_key='conversation:test-fallback',
            anchors=[{'canonical_ref': 'tafsir:ibn-kathir-en:84552', 'source_domain': 'tafsir'}],
        )
        assert saved is not None
        latest = anchor_store.get_latest_anchors_for_session('conversation:test-fallback')
        assert latest is not None
        assert latest.backend == 'sqlite'
    finally:
        settings.anchor_store_backend = old_backend
        settings.anchor_store_sqlite_path = old_path
        anchor_store._SQLITE_READY = old_ready
