from __future__ import annotations

EXCERPT_TARGET_CHARS = 600
EXCERPT_MIN_CHARS = 450
EXCERPT_MAX_CHARS = 700



def build_tafsir_excerpt(text: str, *, target_chars: int = EXCERPT_TARGET_CHARS) -> tuple[str, bool]:
    text = " ".join((text or "").split()).strip()
    if not text:
        return "", False

    target = max(EXCERPT_MIN_CHARS, min(EXCERPT_MAX_CHARS, int(target_chars)))
    if len(text) <= target:
        return text, False

    for punct in (". ", "! ", "? ", "; ", ": "):
        idx = text.rfind(punct, 0, target + 1)
        if idx >= EXCERPT_MIN_CHARS:
            cut = idx + 1
            return text[:cut].strip(), True

    space_idx = text.rfind(" ", 0, target + 1)
    if space_idx >= EXCERPT_MIN_CHARS:
        return text[:space_idx].rstrip(), True

    return text[:target].rstrip(), True
