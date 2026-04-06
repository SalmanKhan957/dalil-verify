from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    'SOURCE_REGISTRY': ('services.source_registry.registry', 'SOURCE_REGISTRY'),
    'SOURCE_REGISTRY_BOOTSTRAP': ('services.source_registry.registry', 'SOURCE_REGISTRY_BOOTSTRAP'),
    'get_default_tafsir_source_for_explain': ('services.source_registry.registry', 'get_default_tafsir_source_for_explain'),
    'get_source_record': ('services.source_registry.registry', 'get_source_record'),
    'get_source_records_by_domain': ('services.source_registry.registry', 'get_source_records_by_domain'),
    'is_source_enabled': ('services.source_registry.registry', 'is_source_enabled'),
    'resolve_tafsir_source_for_explain': ('services.source_registry.registry', 'resolve_tafsir_source_for_explain'),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:  # pragma: no cover
        raise AttributeError(name) from exc
    return getattr(import_module(module_name), attr_name)
