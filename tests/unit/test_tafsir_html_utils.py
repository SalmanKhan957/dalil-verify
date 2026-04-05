from domains.tafsir.html_utils import compute_text_hash, normalize_search_text, strip_html_to_text


def test_strip_html_to_text_preserves_readable_breaks() -> None:
    value = "<h2>Heading</h2><p>First paragraph.</p><p>Second paragraph.</p>"
    assert strip_html_to_text(value) == "Heading\n\nFirst paragraph.\n\nSecond paragraph."


def test_normalize_search_text_collapses_whitespace() -> None:
    assert normalize_search_text("  a\n\n b   c ") == "a b c"


def test_compute_text_hash_is_stable() -> None:
    assert compute_text_hash("abc") == compute_text_hash("abc")
