from __future__ import annotations

import re
from typing import Any

VERSE_ORNAMENT_RE = re.compile(r"[﴿﴾]")
SPECIAL_MARK_RE = re.compile(r"[۞۩]")
WASLA_ALIF_RE = re.compile(r"ٱ")
QURANIC_ANNOTATION_RE = re.compile(r"[ۣ۪ۭ۟۠ۡۢۤۧۨ۫۬]")
ARABIC_INDIC_DIGIT_RE = re.compile(r"[٠-٩۰-۹]")
SMALL_HIGH_SIGNS_RE = re.compile(r"[ٰٕٖٜٟٔٗ٘ٙٚٛٝٞۖۗۘۙۚۛۜ]")

ROUTE_UTHMANI_FIRST = "UTHMANI_FIRST"
ROUTE_SIMPLE_FIRST = "SIMPLE_FIRST"
ROUTE_AMBIGUOUS_BOTH = "AMBIGUOUS_BOTH"


def detect_quran_query_route(raw_query: str) -> dict[str, Any]:
    text = (raw_query or "").strip()
    if not text:
        return {
            "route": ROUTE_SIMPLE_FIRST,
            "uthmani_score": 0,
            "strong_score": 0,
            "weak_score": 0,
            "indicators": [],
        }

    indicators: list[str] = []
    strong_score = 0
    weak_score = 0

    verse_ornaments = len(VERSE_ORNAMENT_RE.findall(text))
    if verse_ornaments:
        indicators.append("verse_ornaments")
        weak_score += 1

    special_marks = len(SPECIAL_MARK_RE.findall(text))
    if special_marks:
        indicators.append("special_marks")
        # treat as weak transport/layout signal unless reinforced by real Uthmani markers
        weak_score += 1

    wasla_alif_count = len(WASLA_ALIF_RE.findall(text))
    if wasla_alif_count:
        indicators.append("wasla_alif")
        strong_score += 5

    annotation_count = len(QURANIC_ANNOTATION_RE.findall(text))
    if annotation_count >= 2:
        indicators.append("quranic_annotations")
        strong_score += 4

    arabic_indic_digits = len(ARABIC_INDIC_DIGIT_RE.findall(text))
    if arabic_indic_digits >= 2:
        indicators.append("arabic_indic_digits")
        weak_score += 1

    small_high_signs = len(SMALL_HIGH_SIGNS_RE.findall(text))
    if small_high_signs >= 4:
        indicators.append("small_high_signs")
        weak_score += 1

    total_score = strong_score + weak_score

    # Professional routing rule:
    # - only genuine Uthmani markers (wasla / annotation signs) should force UTHMANI_FIRST
    # - ornaments, digits, waqf glyphs, and tashkeel-like high signs alone should not drag simple text into ambiguous routing
    if wasla_alif_count > 0 or annotation_count >= 2:
        route = ROUTE_UTHMANI_FIRST
    elif strong_score >= 3:
        route = ROUTE_AMBIGUOUS_BOTH
    else:
        route = ROUTE_SIMPLE_FIRST

    return {
        "route": route,
        "uthmani_score": total_score,
        "strong_score": strong_score,
        "weak_score": weak_score,
        "indicators": indicators,
        "counts": {
            "verse_ornaments": verse_ornaments,
            "special_marks": special_marks,
            "wasla_alif": wasla_alif_count,
            "quranic_annotations": annotation_count,
            "arabic_indic_digits": arabic_indic_digits,
            "small_high_signs": small_high_signs,
        },
    }
