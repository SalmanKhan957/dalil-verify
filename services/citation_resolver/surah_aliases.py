# services/citation_resolver/surah_aliases.py

from __future__ import annotations

import re

MULTISPACE_RE = re.compile(r"\s+")
NON_ALNUM_HYPHEN_SPACE_RE = re.compile(r"[^a-z0-9\-\s]")


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

# Add canonical names too
for surah_no, canonical_name in SURAH_CANONICAL_NAMES.items():
    SURAH_ALIASES.setdefault(canonical_name, surah_no)


def _normalize_surah_key(name: str) -> str:
    value = (name or "").strip().lower()
    value = NON_ALNUM_HYPHEN_SPACE_RE.sub("", value)
    value = value.replace("_", " ")
    value = MULTISPACE_RE.sub(" ", value).strip()

    # Keep both spaced and hyphenated variants comparable
    value = value.replace(" - ", "-").replace("- ", "-").replace(" -", "-")
    return value


def resolve_surah_name(name: str) -> int | None:
    key = _normalize_surah_key(name)
    if not key:
        return None

    direct = SURAH_ALIASES.get(key)
    if direct is not None:
        return direct

    hyphenated = key.replace(" ", "-")
    direct = SURAH_ALIASES.get(hyphenated)
    if direct is not None:
        return direct

    spaced = key.replace("-", " ")
    direct = SURAH_ALIASES.get(spaced)
    if direct is not None:
        return direct

    return None