from __future__ import annotations

import json
from pathlib import Path


MAPPING_PATH = Path(__file__).with_name('hadith_topical_mapping.json')


def load_hadith_topical_mapping() -> dict:
    return json.loads(MAPPING_PATH.read_text(encoding='utf-8'))
