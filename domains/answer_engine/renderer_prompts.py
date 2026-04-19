from __future__ import annotations

import json
from typing import Any


DALIL_RENDERER_SYSTEM_PROMPT = """You are DALIL's renderer.
You are not a router, retriever, policy engine, or scholar.
You must only phrase the answer using the supplied DALIL composition packet.
Rules:
- Preserve Quran, Tafsir, and Hadith boundaries explicitly.
- Do not add evidence, citations, or claims that are not present in the packet.
- If the packet says abstain, keep the abstention.
- If the packet says clarify, keep the clarification.
- Start with the direct answer in plain language.
- Make the answer feel like a capable chat assistant, not a report generator.
- For Quran with tafsir, give a brief meaning-first explanation and then clearly separate short tafsir-source sentences.
- For hadith explanation, sound natural and practical without becoming casual or preachy.
- Do not mention internal pipeline language such as 'retrieved', 'attached below', 'anchored to this scope', or 'per-source emphasis'.
- Do not start source summaries with raw heading fragments such as 'The Virtue of...' or 'On "...":'.
- If continuation_controls specifies truncate_large_responses, strictly limit paragraph output and append the offered_continuation_hook exactly as provided.
- Keep the tone natural, calm, and readable.
- Prefer concise, readable language.
- Return valid JSON only.
"""


def build_renderer_user_prompt(*, composition: dict[str, Any], deterministic_answer_text: str | None) -> str:
    continuation = composition.get('continuation_controls') if isinstance(composition, dict) else None
    quality_bar: dict[str, Any] = {
        'meaning_first': True,
        'direct_answer_first': True,
        'source_boundaries_explicit': True,
        'no_pipeline_jargon': True,
        'short_surah_explanations_should_sound_natural': True,
        'chat_like_but_bounded': True,
    }
    if isinstance(continuation, dict) and continuation.get('truncate_large_responses'):
        hook = continuation.get('offered_continuation_hook')
        if hook:
            quality_bar['append_continuation_hook'] = str(hook)
            quality_bar['max_paragraphs'] = int(continuation.get('max_allowed_paragraphs') or 5)

    payload: dict[str, Any] = {
        'composition': composition,
        'deterministic_answer_text': deterministic_answer_text or '',
        'task': {
            'goal': 'Produce a polished, source-grounded final answer and a short list of contextual follow-up suggestions.',
            'output_contract': {
                'answer_text': 'string',
                'followup_suggestions': ['string'],
                'style_applied': 'string',
            },
            'quality_bar': quality_bar,
        },
    }
    return json.dumps(payload, ensure_ascii=False)
