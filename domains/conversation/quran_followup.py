from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QuranReference:
    canonical_ref: str
    surah_no: int
    ayah_start: int
    ayah_end: int

    @property
    def is_span(self) -> bool:
        return self.ayah_end != self.ayah_start

    @property
    def span_length(self) -> int:
        return (self.ayah_end - self.ayah_start) + 1


def build_quran_ref(surah_no: int, ayah_start: int, ayah_end: int | None = None) -> str:
    end = ayah_start if ayah_end is None else ayah_end
    if end == ayah_start:
        return f'quran:{surah_no}:{ayah_start}'
    return f'quran:{surah_no}:{ayah_start}-{end}'


def parse_quran_ref(value: str | None) -> QuranReference | None:
    cleaned = str(value or '').strip()
    if not cleaned.startswith('quran:'):
        return None
    body = cleaned[len('quran:'):]
    parts = body.split(':', 1)
    if len(parts) != 2:
        return None
    surah_text, ayah_text = parts
    try:
        surah_no = int(surah_text)
    except ValueError:
        return None
    if '-' in ayah_text:
        start_text, end_text = ayah_text.split('-', 1)
    else:
        start_text, end_text = ayah_text, ayah_text
    try:
        ayah_start = int(start_text)
        ayah_end = int(end_text)
    except ValueError:
        return None
    if ayah_end < ayah_start:
        ayah_start, ayah_end = ayah_end, ayah_start
    return QuranReference(
        canonical_ref=build_quran_ref(surah_no, ayah_start, ayah_end),
        surah_no=surah_no,
        ayah_start=ayah_start,
        ayah_end=ayah_end,
    )


def contains_ref(container_ref: str | None, value_ref: str | None) -> bool:
    container = parse_quran_ref(container_ref)
    value = parse_quran_ref(value_ref)
    if container is None or value is None:
        return False
    return (
        container.surah_no == value.surah_no
        and container.ayah_start <= value.ayah_start
        and container.ayah_end >= value.ayah_end
    )


def ordinal_ref(span_ref: str | None, ordinal: str) -> str | None:
    parsed = parse_quran_ref(span_ref)
    if parsed is None:
        return None
    key = str(ordinal or '').strip().lower()
    ordinal_map = {
        'first': 1,
        '1st': 1,
        'second': 2,
        '2nd': 2,
        'third': 3,
        '3rd': 3,
        'fourth': 4,
        '4th': 4,
    }
    if key == 'last':
        return build_quran_ref(parsed.surah_no, parsed.ayah_end)
    offset = ordinal_map.get(key)
    if offset is None or offset > parsed.span_length:
        return None
    return build_quran_ref(parsed.surah_no, parsed.ayah_start + offset - 1)


def available_ordinals(span_ref: str | None) -> list[tuple[str, str]]:
    parsed = parse_quran_ref(span_ref)
    if parsed is None or parsed.span_length <= 1:
        return []
    labels: list[str] = ['first', 'second', 'third', 'fourth']
    items: list[tuple[str, str]] = []
    for label in labels:
        target = ordinal_ref(parsed.canonical_ref, label)
        if target is not None:
            items.append((label, target))
    last_target = ordinal_ref(parsed.canonical_ref, 'last')
    if last_target is not None and all(existing != last_target for _, existing in items):
        items.append(('last', last_target))
    return items


def adjacent_ref(current_ref: str | None, direction: str) -> str | None:
    parsed = parse_quran_ref(current_ref)
    if parsed is None:
        return None
    key = str(direction or '').strip().lower()
    if key in {'previous', 'prev', 'before'}:
        target_ayah = max(1, parsed.ayah_start - 1)
    else:
        target_ayah = parsed.ayah_end + 1
    return build_quran_ref(parsed.surah_no, target_ayah)
