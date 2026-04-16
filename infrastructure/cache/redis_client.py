from __future__ import annotations

from typing import Any

from infrastructure.config.settings import settings

_REDIS_CLIENT: Any | None = None
_REDIS_TARGET: tuple[str, float] | None = None


class RedisUnavailableError(RuntimeError):
    pass



def reset_redis_client() -> None:
    global _REDIS_CLIENT, _REDIS_TARGET
    client = _REDIS_CLIENT
    _REDIS_CLIENT = None
    _REDIS_TARGET = None
    close = getattr(client, 'close', None)
    if callable(close):
        try:
            close()
        except Exception:
            pass



def get_anchor_store_redis_client() -> Any:
    global _REDIS_CLIENT, _REDIS_TARGET
    target = (
        str(settings.anchor_store_redis_url or '').strip() or 'redis://127.0.0.1:6379/0',
        float(getattr(settings, 'anchor_store_redis_socket_timeout_seconds', 1.5) or 1.5),
    )
    if _REDIS_CLIENT is not None and _REDIS_TARGET == target:
        return _REDIS_CLIENT
    try:
        from redis import Redis
    except Exception as exc:  # pragma: no cover
        raise RedisUnavailableError('redis package is not installed') from exc

    client = Redis.from_url(
        target[0],
        decode_responses=True,
        socket_timeout=target[1],
        socket_connect_timeout=target[1],
        health_check_interval=30,
    )
    client.ping()
    _REDIS_CLIENT = client
    _REDIS_TARGET = target
    return client
