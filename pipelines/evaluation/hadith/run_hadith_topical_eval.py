from __future__ import annotations

import json
from pathlib import Path

from pipelines.evaluation.hadith.contracts import HadithTopicalJudgment


def load_judgments(path: str | Path) -> list[HadithTopicalJudgment]:
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    judgments = []
    for item in raw:
        judgments.append(
            HadithTopicalJudgment(
                query_text=str(item['query_text']),
                expected_topics=tuple(item.get('expected_topics') or ()),
                expected_profile=str(item.get('expected_profile') or 'general_topic'),
                acceptable_refs=tuple(item.get('acceptable_refs') or ()),
                bad_refs=tuple(item.get('bad_refs') or ()),
                notes=str(item.get('notes') or ''),
            )
        )
    return judgments
