from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "build_health_payload": ("domains.quran.verifier.service", "build_health_payload"),
    "verify_quran_text": ("domains.quran.verifier.service", "verify_quran_text"),
    "bootstrap": ("domains.quran.verifier.bootstrap", None),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    return module if attr_name is None else getattr(module, attr_name)
