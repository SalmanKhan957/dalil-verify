from domains.quran.citations.normalizer import normalize_reference_text
from domains.quran.citations.quran_reference_parser import parse_quran_reference
from domains.quran.citations.resolver import resolve_quran_reference
from domains.quran.citations.surah_aliases import resolve_surah_name

__all__ = [
    "normalize_reference_text",
    "parse_quran_reference",
    "resolve_quran_reference",
    "resolve_surah_name",
]
