from __future__ import annotations

"""Compatibility shim.

Runtime ownership now lives outside scripts.common. Keep this module only
for legacy script imports until the remaining script-era callers are retired.
"""

from domains.quran.verifier.internal.quran_span_index import *  # noqa: F401,F403
