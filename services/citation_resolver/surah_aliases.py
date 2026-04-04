from __future__ import annotations

import re
from dataclasses import dataclass

MULTISPACE_RE = re.compile(r"\s+")
NON_ALNUM_HYPHEN_SPACE_RE = re.compile(r"[^a-z0-9\-\s']")
SURAH_PREFIX_RE = re.compile(r"^(?:surah|surat|sura|soorah|sorah|chapter)\s+", re.IGNORECASE)
ARTICLE_PREFIX_RE = re.compile(r"^(?:al|an|ar|as|ash|at|ad|az)\s+")
VOWEL_RUN_RE = re.compile(r"(aa|ee|ii|oo|uu)")
DOUBLE_LETTER_RE = re.compile(r"(.)\1+")


SURAH_CANONICAL_NAMES: dict[int, str] = {
    1: "al-fatiha",
    2: "al-baqarah",
    3: "aal-imran",
    4: "an-nisa",
    5: "al-maidah",
    6: "al-anam",
    7: "al-araf",
    8: "al-anfal",
    9: "at-tawbah",
    10: "yunus",
    11: "hud",
    12: "yusuf",
    13: "ar-rad",
    14: "ibrahim",
    15: "al-hijr",
    16: "an-nahl",
    17: "al-isra",
    18: "al-kahf",
    19: "maryam",
    20: "ta-ha",
    21: "al-anbiya",
    22: "al-hajj",
    23: "al-muminun",
    24: "an-nur",
    25: "al-furqan",
    26: "ash-shuara",
    27: "an-naml",
    28: "al-qasas",
    29: "al-ankabut",
    30: "ar-rum",
    31: "luqman",
    32: "as-sajdah",
    33: "al-ahzab",
    34: "saba",
    35: "fatir",
    36: "ya-sin",
    37: "as-saffat",
    38: "sad",
    39: "az-zumar",
    40: "ghafir",
    41: "fussilat",
    42: "ash-shura",
    43: "az-zukhruf",
    44: "ad-dukhan",
    45: "al-jathiyah",
    46: "al-ahqaf",
    47: "muhammad",
    48: "al-fath",
    49: "al-hujurat",
    50: "qaf",
    51: "adh-dhariyat",
    52: "at-tur",
    53: "an-najm",
    54: "al-qamar",
    55: "ar-rahman",
    56: "al-waqiah",
    57: "al-hadid",
    58: "al-mujadilah",
    59: "al-hashr",
    60: "al-mumtahanah",
    61: "as-saff",
    62: "al-jumuah",
    63: "al-munafiqun",
    64: "at-taghabun",
    65: "at-talaq",
    66: "at-tahrim",
    67: "al-mulk",
    68: "al-qalam",
    69: "al-haqqah",
    70: "al-maarij",
    71: "nuh",
    72: "al-jinn",
    73: "al-muzzammil",
    74: "al-muddaththir",
    75: "al-qiyamah",
    76: "al-insan",
    77: "al-mursalat",
    78: "an-naba",
    79: "an-naziat",
    80: "abasa",
    81: "at-takwir",
    82: "al-infitar",
    83: "al-mutaffifin",
    84: "al-inshiqaq",
    85: "al-buruj",
    86: "at-tariq",
    87: "al-ala",
    88: "al-ghashiyah",
    89: "al-fajr",
    90: "al-balad",
    91: "ash-shams",
    92: "al-layl",
    93: "ad-duha",
    94: "ash-sharh",
    95: "at-tin",
    96: "al-alaq",
    97: "al-qadr",
    98: "al-bayyinah",
    99: "az-zalzalah",
    100: "al-adiyat",
    101: "al-qariah",
    102: "at-takathur",
    103: "al-asr",
    104: "al-humazah",
    105: "al-fil",
    106: "quraysh",
    107: "al-maun",
    108: "al-kawthar",
    109: "al-kafirun",
    110: "an-nasr",
    111: "al-masad",
    112: "al-ikhlas",
    113: "al-falaq",
    114: "an-nas",
}

SURAH_ALIASES: dict[str, int] = {
    "fatiha": 1,
    "al-fatiha": 1,
    "fatihah": 1,
    "baqarah": 2,
    "al-baqarah": 2,
    "imran": 3,
    "aal-imran": 3,
    "ali-imran": 3,
    "ya-sin": 36,
    "yasin": 36,
    "ya sin": 36,
    "rahman": 55,
    "ar-rahman": 55,
    "al-rahman": 55,
    "mulk": 67,
    "al-mulk": 67,
    "duha": 93,
    "ad-duha": 93,
    "ash-sharh": 94,
    "al-sharh": 94,
    "sharh": 94,
    "inshirah": 94,
    "al-inshirah": 94,
    "ikhlas": 112,
    "al-ikhlas": 112,
    "falaq": 113,
    "al-falaq": 113,
    "nas": 114,
    "an-nas": 114,
}

for surah_no, canonical_name in SURAH_CANONICAL_NAMES.items():
    SURAH_ALIASES.setdefault(canonical_name, surah_no)


@dataclass(frozen=True)
class SurahAliasEntry:
    surah_no: int
    alias: str
    normalized: str
    compact: str
    skeleton: str


def _normalize_surah_key(name: str) -> str:
    value = (name or "").strip().lower()
    value = value.replace("_", " ")
    value = NON_ALNUM_HYPHEN_SPACE_RE.sub("", value)
    value = value.replace(" - ", "-").replace("- ", "-").replace(" -", "-")
    value = value.replace("-", " ")
    value = MULTISPACE_RE.sub(" ", value).strip()
    value = SURAH_PREFIX_RE.sub("", value).strip()
    return value


def _drop_leading_article(value: str) -> str:
    return ARTICLE_PREFIX_RE.sub("", value).strip()


def _compact(value: str) -> str:
    return value.replace(" ", "").replace("-", "")


def _build_skeleton(value: str) -> str:
    skeleton = _normalize_surah_key(value)
    skeleton = _drop_leading_article(skeleton)
    skeleton = _compact(skeleton)
    skeleton = VOWEL_RUN_RE.sub(lambda m: m.group(0)[0], skeleton)
    skeleton = (
        skeleton.replace("aa", "a")
        .replace("ee", "i")
        .replace("ii", "i")
        .replace("oo", "u")
        .replace("uu", "u")
        .replace("ou", "u")
        .replace("ow", "u")
        .replace("ph", "f")
        .replace("q", "k")
        .replace("dh", "d")
        .replace("th", "t")
        .replace("tz", "z")
    )
    skeleton = DOUBLE_LETTER_RE.sub(r"\1", skeleton)
    return skeleton


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            ))
        prev = curr
    return prev[-1]


def _allowed_distance(length: int) -> int:
    if length <= 4:
        return 0
    if length <= 7:
        return 1
    if length <= 11:
        return 2
    return 3


def _iter_alias_variants(alias: str) -> set[str]:
    normalized = _normalize_surah_key(alias)
    variants = {normalized}
    if normalized:
        variants.add(normalized.replace(" ", "-"))
        variants.add(normalized.replace("-", " "))
        variants.add(_drop_leading_article(normalized))
    return {v for v in variants if v}


def _build_alias_entries() -> list[SurahAliasEntry]:
    entries: list[SurahAliasEntry] = []
    seen: set[tuple[int, str]] = set()
    for alias, surah_no in SURAH_ALIASES.items():
        for variant in _iter_alias_variants(alias):
            compact = _compact(variant)
            entry = SurahAliasEntry(
                surah_no=surah_no,
                alias=variant,
                normalized=variant,
                compact=compact,
                skeleton=_build_skeleton(variant),
            )
            key = (entry.surah_no, entry.normalized)
            if key not in seen:
                entries.append(entry)
                seen.add(key)
    return entries


_ALIAS_ENTRIES = _build_alias_entries()
_NORMALIZED_EXACT_MAP: dict[str, int] = {}
_COMPACT_EXACT_MAP: dict[str, int] = {}
_SKELETON_EXACT_MAP: dict[str, int] = {}

for entry in _ALIAS_ENTRIES:
    _NORMALIZED_EXACT_MAP.setdefault(entry.normalized, entry.surah_no)
    _COMPACT_EXACT_MAP.setdefault(entry.compact, entry.surah_no)
    # only keep skeleton exacts that are unambiguous
    existing = _SKELETON_EXACT_MAP.get(entry.skeleton)
    if existing is None:
        _SKELETON_EXACT_MAP[entry.skeleton] = entry.surah_no
    elif existing != entry.surah_no:
        _SKELETON_EXACT_MAP[entry.skeleton] = -1


def resolve_surah_name(name: str) -> int | None:
    key = _normalize_surah_key(name)
    if not key:
        return None

    direct = _NORMALIZED_EXACT_MAP.get(key)
    if direct is not None:
        return direct

    hyphenated = key.replace(" ", "-")
    direct = _NORMALIZED_EXACT_MAP.get(hyphenated)
    if direct is not None:
        return direct

    compact = _compact(key)
    direct = _COMPACT_EXACT_MAP.get(compact)
    if direct is not None:
        return direct

    skeleton = _build_skeleton(key)
    skeleton_match = _SKELETON_EXACT_MAP.get(skeleton)
    if skeleton_match is not None and skeleton_match > 0:
        return skeleton_match

    # Bounded fuzzy match: only over surah aliases, only when the input looks like a surah name.
    token_count = len(key.split())
    if token_count > 4 or len(compact) < 5:
        return None

    best_entry: SurahAliasEntry | None = None
    best_distance: int | None = None
    second_best_distance: int | None = None

    for entry in _ALIAS_ENTRIES:
        distance = _edit_distance(skeleton, entry.skeleton)
        if distance > _allowed_distance(max(len(skeleton), len(entry.skeleton))):
            continue
        if best_distance is None or distance < best_distance:
            second_best_distance = best_distance
            best_distance = distance
            best_entry = entry
        elif second_best_distance is None or distance < second_best_distance:
            second_best_distance = distance

    if best_entry is None or best_distance is None:
        return None

    if second_best_distance is not None and second_best_distance == best_distance:
        return None

    return best_entry.surah_no
