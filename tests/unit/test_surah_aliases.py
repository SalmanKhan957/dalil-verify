
from domains.quran.citations.surah_aliases import resolve_surah_name


def test_resolve_surah_name_ikhlas():
    assert resolve_surah_name("ikhlas") == 112
    assert resolve_surah_name("al-ikhlas") == 112


def test_resolve_surah_name_ash_sharh_variants():
    assert resolve_surah_name("ash-sharh") == 94
    assert resolve_surah_name("inshirah") == 94
    assert resolve_surah_name("al-inshirah") == 94


def test_resolve_surah_name_mulk():
    assert resolve_surah_name("mulk") == 67
    assert resolve_surah_name("al-mulk") == 67


def test_resolve_surah_name_unknown():
    assert resolve_surah_name("fake-surah-name") is None