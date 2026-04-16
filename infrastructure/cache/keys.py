from __future__ import annotations


def _clean_namespace(namespace: str) -> str:
    cleaned = str(namespace or '').strip().strip(':')
    return cleaned or 'dalil:conversation'


def anchor_session_key(*, namespace: str, session_key: str) -> str:
    return f"{_clean_namespace(namespace)}:session:{session_key}"


def anchor_turn_key(*, namespace: str, turn_id: str) -> str:
    return f"{_clean_namespace(namespace)}:turn:{turn_id}"
