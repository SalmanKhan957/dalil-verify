from __future__ import annotations

from services.quran_runtime.long_span_fastpath import (
    build_long_span_debug_block,
    is_long_span_fastpath_enabled,
    try_long_span_exact_match,
)

__all__ = [
    "build_long_span_debug_block",
    "is_long_span_fastpath_enabled",
    "try_long_span_exact_match",
]
