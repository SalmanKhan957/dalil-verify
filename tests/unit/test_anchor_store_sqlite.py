from __future__ import annotations

from domains.conversation import anchor_store
from infrastructure.config.settings import settings


def test_sqlite_anchor_store_round_trip(tmp_path) -> None:
    old_backend = settings.anchor_store_backend
    old_path = settings.anchor_store_sqlite_path
    old_ready = anchor_store._SQLITE_READY
    try:
        settings.anchor_store_backend = 'sqlite'
        settings.anchor_store_sqlite_path = tmp_path / 'anchor_store.sqlite3'
        anchor_store._SQLITE_READY = False

        saved = anchor_store.save_response_anchors(
            session_key='conversation:test',
            anchors=[{'canonical_ref': 'quran:112:1-4', 'domain': 'quran'}],
        )
        assert saved is not None

        latest = anchor_store.get_latest_anchors_for_session('conversation:test')
        assert latest is not None
        assert latest.anchor_refs == ['quran:112:1-4']

        by_turn = anchor_store.get_anchors_for_parent_turn(saved.turn_id)
        assert by_turn is not None
        assert by_turn.anchor_refs == ['quran:112:1-4']
    finally:
        settings.anchor_store_backend = old_backend
        settings.anchor_store_sqlite_path = old_path
        anchor_store._SQLITE_READY = old_ready
