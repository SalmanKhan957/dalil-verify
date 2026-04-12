from __future__ import annotations

import re
from typing import Any

from infrastructure.config.settings import settings


def _collapse(text: Any) -> str:
    return ' '.join(str(text or '').split()).strip()


def _truncate(text: str, *, limit: int = 320) -> str:
    text = _collapse(text)
    if not text:
        return ''
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for delimiter in ('. ', '; ', ', ', ' '):
        idx = cut.rfind(delimiter)
        if idx >= int(limit * 0.6):
            cut = cut[:idx]
            break
    return cut.rstrip(' ,;:-') + '…'


def _first_bundle(composition: dict[str, Any], domain: str) -> dict[str, Any] | None:
    for bundle in list(composition.get('source_bundles') or []):
        if str(bundle.get('domain') or '') == domain:
            return bundle
    return None


def _bundles(composition: dict[str, Any], domain: str) -> list[dict[str, Any]]:
    return [bundle for bundle in list(composition.get('source_bundles') or []) if str(bundle.get('domain') or '') == domain]


def _bundle_extract(bundle: dict[str, Any]) -> str:
    return _collapse(bundle.get('focused_extract') or bundle.get('summary_point') or bundle.get('short_excerpt') or bundle.get('full_text'))


def _sentences(text: str) -> list[str]:
    normalized = _collapse(text)
    if not normalized:
        return []
    parts = re.split(r'(?<=[.!?])\s+', normalized)
    return [part.strip() for part in parts if part.strip()]


def _source_label(bundle: dict[str, Any]) -> str:
    return _collapse(bundle.get('display_name')) or _collapse(bundle.get('source_id')) or 'Source'


def _verbosity_limit(preferred: str | None, *, default: int, brief: int, detailed: int) -> int:
    verbosity = _collapse(preferred).lower() or settings.renderer_verbosity_default
    if verbosity in {'brief', 'short'}:
        return brief
    if verbosity in {'detailed', 'long'}:
        return detailed
    return default


def _rendering_pref(composition: dict[str, Any], key: str, default: str) -> str:
    rendering = dict(composition.get('rendering') or {})
    return _collapse(rendering.get(key)) or default


def _lead_from_seed(composition: dict[str, Any], *, fallback: str = '') -> str:
    seed = dict(composition.get('answer_seed') or {})
    return _collapse(seed.get('lead_text')) or _collapse(fallback)


def _seed_meaning_summary(composition: dict[str, Any]) -> str:
    seed = dict(composition.get('answer_seed') or {})
    return _collapse(seed.get('meaning_summary'))


def _clean_lead(text: str) -> str:
    lowered = text.lower()
    for noisy in ('retrieved commentary', 'per-source emphasis:', 'is attached below'):
        idx = lowered.find(noisy)
        if idx >= 0:
            text = text[:idx].rstrip(' .;:')
            lowered = text.lower()
    return text


def _normalize_point_text(text: str, *, limit: int) -> str:
    normalized = _collapse(text)
    if not normalized:
        return ''
    normalized = re.sub(r'^On\s+[“\"].+?[”\"]\s*:\s*', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'^(The\s+(?:Virtue|Virtues|Merits)\s+of[^.]*\.?\s*)', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'^[A-Z][^:]{0,70}:\s*', '', normalized)
    sentences = _sentences(normalized)
    normalized = sentences[0] if sentences else normalized
    return _truncate(normalized, limit=limit)


def _comparative_point_map(composition: dict[str, Any]) -> dict[str, str]:
    comparative = dict(composition.get('comparative') or {})
    mapping: dict[str, str] = {}
    for item in list(composition.get('source_bundles') or []):
        source_id = _collapse(item.get('source_id'))
        point = _collapse(item.get('summary_point'))
        if source_id and point:
            mapping[source_id] = point
    for item in list(comparative.get('distinct_emphases') or []):
        source_id = _collapse(item.get('source_id'))
        points = [_collapse(point) for point in list(item.get('points') or []) if _collapse(point)]
        if source_id and points:
            mapping[source_id] = points[0]
    return mapping


def _tafsir_connector(label: str) -> str:
    lowered = label.lower()
    if 'tafheem' in lowered:
        return 'explains'
    if 'ma\'arif' in lowered or 'maarif' in lowered:
        return 'highlights'
    if 'ibn kathir' in lowered:
        return 'emphasizes'
    return 'explains'


def _render_tafsir_source_sentences(composition: dict[str, Any], tafsir_bundles: list[dict[str, Any]], *, max_items: int = 3, limit: int = 220) -> list[str]:
    rendered: list[str] = []
    point_map = _comparative_point_map(composition)
    for bundle in tafsir_bundles[:max_items]:
        label = _source_label(bundle)
        point = point_map.get(_collapse(bundle.get('source_id'))) or _collapse(bundle.get('summary_point')) or _bundle_extract(bundle)
        extract = _normalize_point_text(point, limit=limit)
        if not extract:
            continue
        if len(extract) > 1:
            extract = extract[0].lower() + extract[1:]
        rendered.append(f'{label} {_tafsir_connector(label)} that {extract}')
    return rendered


def render_quran_text(composition: dict[str, Any], *, fallback: str | None) -> str | None:
    scope = dict(composition.get('resolved_scope') or {})
    quran_bundle = _first_bundle(composition, 'quran') or {}
    span = _collapse(scope.get('span_label')) or _collapse(quran_bundle.get('display_name')) or 'This Quran passage'
    excerpt = _collapse(quran_bundle.get('focused_extract') or quran_bundle.get('short_excerpt') or quran_bundle.get('full_text'))
    if not excerpt:
        return fallback
    return f'{span} says: {excerpt}'


def render_quran_explanation(composition: dict[str, Any], *, fallback: str | None) -> str | None:
    scope = dict(composition.get('resolved_scope') or {})
    quran_bundle = _first_bundle(composition, 'quran') or {}
    span = _collapse(scope.get('span_label')) or _collapse(quran_bundle.get('display_name')) or 'This Quran passage'
    excerpt = _collapse(quran_bundle.get('focused_extract') or quran_bundle.get('short_excerpt') or quran_bundle.get('full_text'))
    meaning_summary = _seed_meaning_summary(composition)
    limit = _verbosity_limit(_rendering_pref(composition, 'verbosity', 'standard'), default=260, brief=180, detailed=420)
    if meaning_summary:
        return f'{span} teaches that {_truncate(meaning_summary, limit=limit)}'
    if not excerpt:
        return fallback
    return f'{span} teaches that {_truncate(excerpt, limit=limit)}'


def render_quran_with_tafsir(composition: dict[str, Any], *, fallback: str | None) -> str | None:
    scope = dict(composition.get('resolved_scope') or {})
    span = _collapse(scope.get('span_label')) or 'this Quran passage'
    quran_bundle = _first_bundle(composition, 'quran') or {}
    quote = _collapse(quran_bundle.get('focused_extract') or quran_bundle.get('short_excerpt') or quran_bundle.get('full_text'))
    tafsir_bundles = _bundles(composition, 'tafsir')
    lead = _clean_lead(_lead_from_seed(composition, fallback=''))
    meaning_summary = _seed_meaning_summary(composition)
    verbosity = _rendering_pref(composition, 'verbosity', 'standard')
    lead_limit = _verbosity_limit(verbosity, default=260, brief=210, detailed=360)
    per_source_limit = _verbosity_limit(verbosity, default=180, brief=135, detailed=250)

    parts: list[str] = []
    if meaning_summary:
        parts.append(_truncate(meaning_summary, limit=lead_limit))
    elif lead:
        parts.append(_truncate(lead, limit=lead_limit))
    elif quote:
        parts.append(f'{span} teaches that {_truncate(quote, limit=lead_limit)}')

    parts.extend(_render_tafsir_source_sentences(composition, tafsir_bundles, limit=per_source_limit))

    rendered = ' '.join(part.rstrip('.') + '.' for part in parts if part).strip()
    return rendered or fallback


def render_hadith_text(composition: dict[str, Any], *, fallback: str | None) -> str | None:
    scope = dict(composition.get('resolved_scope') or {})
    hadith_bundle = _first_bundle(composition, 'hadith') or {}
    label = _collapse(scope.get('public_ref_label')) or _collapse(hadith_bundle.get('display_name')) or 'This hadith'
    text = _collapse(hadith_bundle.get('full_text') or hadith_bundle.get('focused_extract') or hadith_bundle.get('short_excerpt'))
    if not text:
        return fallback
    return f'{label}: {text}'


def render_hadith_explanation(composition: dict[str, Any], *, fallback: str | None) -> str | None:
    scope = dict(composition.get('resolved_scope') or {})
    hadith_bundle = _first_bundle(composition, 'hadith') or {}
    label = _collapse(scope.get('public_ref_label')) or _collapse(hadith_bundle.get('display_name')) or 'This hadith'
    lead = _clean_lead(_lead_from_seed(composition, fallback=''))
    takeaways = list((composition.get('answer_seed') or {}).get('key_takeaways') or [])
    focused = _collapse(hadith_bundle.get('focused_extract') or hadith_bundle.get('short_excerpt'))
    parts: list[str] = []
    if lead:
        parts.append(_truncate(lead, limit=320))
    elif focused:
        parts.append(f'{label} teaches that {_truncate(focused, limit=320)}')
    else:
        parts.append(f'{label} has been retrieved from the anchored source text.')
    if takeaways:
        summary = '; '.join(_truncate(str(item), limit=120) for item in takeaways[:3] if str(item).strip())
        if summary:
            parts.append(f'In simple terms: {summary}.')
    return ' '.join(part for part in parts if part).strip() or fallback


def render_clarify(composition: dict[str, Any], *, fallback: str | None) -> str | None:
    clarification = dict(composition.get('clarification') or {})
    prompt = _collapse(clarification.get('prompt'))
    topics = [str(item).strip() for item in list(clarification.get('suggested_topics') or []) if str(item).strip()]
    if prompt and topics:
        if len(topics) == 1:
            return f'{prompt} You could ask about {topics[0]}.'
        return f"{prompt} You could ask about {', '.join(topics[:-1])}, or {topics[-1]}."
    return prompt or fallback


def render_abstain(composition: dict[str, Any], *, fallback: str | None) -> str | None:
    abstention = dict(composition.get('abstention') or {})
    message = _collapse(abstention.get('safe_user_message'))
    next_actions = [str(item).strip() for item in list(abstention.get('next_supported_actions') or []) if str(item).strip()]
    if message and next_actions:
        return f"{message} Supported next steps: {'; '.join(next_actions)}."
    return message or fallback


def render_followup_tafsir(composition: dict[str, Any], *, fallback: str | None) -> str | None:
    scope = dict(composition.get('resolved_scope') or {})
    span = _collapse(scope.get('span_label')) or 'the current Quran passage'
    tafsir_bundles = _bundles(composition, 'tafsir')
    if not tafsir_bundles:
        return fallback
    selected = tafsir_bundles[0]
    label = _source_label(selected)
    focused = _normalize_point_text(_bundle_extract(selected), limit=340)
    if not focused:
        return fallback
    if len(focused) > 1:
        focused = focused[0].lower() + focused[1:]
    return f'For {span}, {label} explains that {focused}.'


def render_followup_quran(composition: dict[str, Any], *, fallback: str | None) -> str | None:
    quran_bundle = _first_bundle(composition, 'quran') or {}
    scope = dict(composition.get('resolved_scope') or {})
    span = _collapse(scope.get('span_label')) or 'the current verse span'
    focused = _collapse(quran_bundle.get('focused_extract') or quran_bundle.get('short_excerpt') or quran_bundle.get('full_text'))
    if not focused:
        return fallback
    return f'Within {span}, the requested part says: {_truncate(focused, limit=340)}'


def render_followup_hadith(composition: dict[str, Any], *, fallback: str | None) -> str | None:
    return render_hadith_explanation(composition, fallback=fallback)


def suggest_followups(composition: dict[str, Any], *, route_type: str, render_mode: str) -> list[str]:
    if not settings.renderer_followups_enabled:
        return []
    followup = dict(composition.get('followup') or {})
    suggestions = [str(item).strip() for item in list(followup.get('suggested_followups') or []) if str(item).strip()]
    if suggestions:
        return suggestions[:4]
    source_specific = [str(item).strip() for item in list(followup.get('source_specific_followups_supported') or []) if str(item).strip()]
    span_specific = [str(item).strip() for item in list(followup.get('span_specific_followups_supported') or []) if str(item).strip()]
    if route_type.startswith('anchored_followup_'):
        return (span_specific + source_specific)[:4]
    if render_mode in {'quran_with_tafsir', 'quran_explanation', 'quran_text'}:
        return (source_specific + span_specific)[:4]
    if render_mode in {'hadith_text', 'hadith_explanation'}:
        return source_specific[:4]
    return []
