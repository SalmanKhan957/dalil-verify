from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LOG_PATH = Path("logs/verify_quran.jsonl")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_jsonl_log(record: dict[str, Any], log_path: Path = LOG_PATH) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)

    enriched = {
        "timestamp_utc": utc_now_iso(),
        **record,
    }

    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(enriched, ensure_ascii=False) + "\n")