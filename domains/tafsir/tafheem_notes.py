from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re
from typing import Any

_INLINE_NOTE_RE = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class TafheemNoteEntry:
    anchor_text: str | None
    note_text: str


@dataclass(frozen=True)
class TafheemParsedText:
    display_text: str
    note_entries: tuple[TafheemNoteEntry, ...]
    inline_note_count: int
    commentary_text_plain: str
    commentary_text_html: str


def _normalize_space(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def strip_tafheem_inline_notes(raw_text: str) -> str:
    return _normalize_space(_INLINE_NOTE_RE.sub("", str(raw_text or "")))


def parse_tafheem_raw_text(raw_text: str) -> TafheemParsedText:
    raw_text = str(raw_text or "")
    display_text = strip_tafheem_inline_notes(raw_text)

    note_entries: list[TafheemNoteEntry] = []
    cursor = 0
    for match in _INLINE_NOTE_RE.finditer(raw_text):
        anchor_text = _normalize_space(raw_text[cursor:match.start()])
        note_text = _normalize_space(match.group(1))
        if note_text:
            note_entries.append(
                TafheemNoteEntry(
                    anchor_text=anchor_text or None,
                    note_text=note_text,
                )
            )
        cursor = match.end()

    commentary_blocks: list[str] = []
    html_blocks: list[str] = []
    for entry in note_entries:
        note_text = entry.note_text
        if entry.anchor_text:
            commentary_blocks.append(f'On "{entry.anchor_text}": {note_text}')
            html_blocks.append(
                f"<li><strong>On \u201c{escape(entry.anchor_text)}\u201d:</strong> {escape(note_text)}</li>"
            )
        else:
            commentary_blocks.append(note_text)
            html_blocks.append(f"<li>{escape(note_text)}</li>")

    if commentary_blocks:
        commentary_text_plain = "\n\n".join(commentary_blocks)
        commentary_text_html = "".join(
            [
                f"<p><strong>Verse wording:</strong> {escape(display_text)}</p>" if display_text else "",
                "<h2>Commentary</h2>",
                "<ol>",
                "".join(html_blocks),
                "</ol>",
            ]
        )
    else:
        commentary_text_plain = display_text
        commentary_text_html = escape(display_text)

    return TafheemParsedText(
        display_text=display_text,
        note_entries=tuple(note_entries),
        inline_note_count=len(note_entries),
        commentary_text_plain=commentary_text_plain,
        commentary_text_html=commentary_text_html,
    )


def build_tafheem_render_payload(*, raw_json: dict[str, Any] | None, fallback_text_plain: str | None = None, fallback_text_html: str | None = None) -> dict[str, Any]:
    raw = dict(raw_json or {})

    commentary_text_plain = _normalize_space(str(raw.get("commentary_text_plain") or ""))
    commentary_text_html = str(raw.get("commentary_text_html") or "").strip()
    display_text = _normalize_space(str(raw.get("display_text") or ""))
    inline_note_count = int(raw.get("inline_note_count") or 0)

    if commentary_text_plain and commentary_text_html:
        return {
            "display_text": display_text or _normalize_space(str(fallback_text_plain or "")),
            "excerpt_source_text": commentary_text_plain,
            "text_html": commentary_text_html,
            "inline_note_count": inline_note_count,
            "rendering_mode": "tafheem_commentary_rendered",
        }

    raw_text = str(raw.get("raw_text") or "").strip()
    if raw_text:
        parsed = parse_tafheem_raw_text(raw_text)
        return {
            "display_text": parsed.display_text,
            "excerpt_source_text": parsed.commentary_text_plain,
            "text_html": parsed.commentary_text_html,
            "inline_note_count": parsed.inline_note_count,
            "rendering_mode": "tafheem_commentary_reconstructed",
        }

    fallback_plain = _normalize_space(str(fallback_text_plain or ""))
    fallback_html = str(fallback_text_html or fallback_plain).strip()
    return {
        "display_text": display_text or fallback_plain,
        "excerpt_source_text": fallback_plain,
        "text_html": fallback_html,
        "inline_note_count": inline_note_count,
        "rendering_mode": "stored_text_fallback",
    }


__all__ = [
    "TafheemNoteEntry",
    "TafheemParsedText",
    "build_tafheem_render_payload",
    "parse_tafheem_raw_text",
    "strip_tafheem_inline_notes",
]
