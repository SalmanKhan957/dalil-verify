from __future__ import annotations

from typing import Any

from domains.answer_engine import render_modes
from infrastructure.clients.openai_renderer import render_with_openai
from infrastructure.config.settings import settings


_RENDERER_VERSION = 'bounded_conversational_renderer.v2'


def _mode(composition: dict[str, Any]) -> str:
    return str((composition or {}).get('composition_mode') or '')


def _route_type(payload: dict[str, Any]) -> str:
    return str(payload.get('route_type') or ((payload.get('composition') or {}).get('resolved_scope') or {}).get('route_type') or '')


def _deterministic_render(*, payload: dict[str, Any], fallback_answer_text: str | None) -> dict[str, Any]:
    composition = dict(payload.get('composition') or {})
    mode = _mode(composition)
    route_type = _route_type(payload)

    if route_type == 'anchored_followup_tafsir':
        answer_text = render_modes.render_followup_tafsir(composition, fallback=fallback_answer_text)
        render_mode = 'anchored_followup_tafsir'
    elif route_type == 'anchored_followup_quran':
        answer_text = render_modes.render_followup_quran(composition, fallback=fallback_answer_text)
        render_mode = 'anchored_followup_quran'
    elif route_type == 'anchored_followup_hadith':
        answer_text = render_modes.render_followup_hadith(composition, fallback=fallback_answer_text)
        render_mode = 'anchored_followup_hadith'
    elif mode == 'quran_text':
        answer_text = render_modes.render_quran_text(composition, fallback=fallback_answer_text)
        render_mode = 'quran_text'
    elif mode == 'quran_explanation':
        answer_text = render_modes.render_quran_explanation(composition, fallback=fallback_answer_text)
        render_mode = 'quran_explanation'
    elif mode in {'quran_with_tafsir', 'verification_then_explain'}:
        answer_text = render_modes.render_quran_with_tafsir(composition, fallback=fallback_answer_text)
        render_mode = mode
    elif mode == 'hadith_text':
        answer_text = render_modes.render_hadith_text(composition, fallback=fallback_answer_text)
        render_mode = 'hadith_text'
    elif mode in {'hadith_explanation', 'topical_hadith'}:
        answer_text = render_modes.render_hadith_explanation(composition, fallback=fallback_answer_text)
        render_mode = mode
    elif mode == 'clarify':
        answer_text = render_modes.render_clarify(composition, fallback=fallback_answer_text)
        render_mode = 'clarify'
    elif mode == 'abstain':
        answer_text = render_modes.render_abstain(composition, fallback=fallback_answer_text)
        render_mode = 'abstain'
    else:
        answer_text = fallback_answer_text
        render_mode = mode or 'fallback'

    followup_suggestions = render_modes.suggest_followups(composition, route_type=route_type, render_mode=render_mode)
    return {
        'answer_text': answer_text,
        'render_mode': render_mode,
        'renderer_version': _RENDERER_VERSION,
        'renderer_backend': 'deterministic',
        'followup_suggestions': followup_suggestions,
    }


def render_bounded_conversational_answer(*, payload: dict[str, Any], fallback_answer_text: str | None) -> dict[str, Any]:
    deterministic = _deterministic_render(payload=payload, fallback_answer_text=fallback_answer_text)
    composition = dict(payload.get('composition') or {})

    if settings.renderer_backend != 'openai' or not settings.openai_api_key.strip():
        return deterministic

    rendered = render_with_openai(composition=composition, deterministic_answer_text=deterministic.get('answer_text'))
    if not rendered:
        return deterministic

    return {
        'answer_text': rendered.get('answer_text') or deterministic.get('answer_text'),
        'render_mode': deterministic.get('render_mode'),
        'renderer_version': f'{_RENDERER_VERSION}+openai',
        'renderer_backend': 'openai',
        'followup_suggestions': rendered.get('followup_suggestions') or deterministic.get('followup_suggestions') or [],
        'style_applied': rendered.get('style_applied') or 'openai_renderer',
    }
