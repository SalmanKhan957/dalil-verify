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
- Start with the core meaning in plain language before source-by-source support.
- For Quran with tafsir, give a brief meaning-first explanation and then one short sentence per tafsir source.
- Do not mention internal pipeline language such as 'retrieved', 'attached below', 'anchored to this scope', or 'per-source emphasis'.
- Do not start source summaries with raw heading fragments such as 'The Virtue of...' or 'On \"...\":'.
- Keep the tone natural and assistant-like, but not chatty or casual.
- Prefer concise, readable language.
- Return valid JSON only.
"""


def build_renderer_user_prompt(*, composition: dict[str, Any], deterministic_answer_text: str | None) -> str:
    payload = {
        'composition': composition,
        'deterministic_answer_text': deterministic_answer_text or '',
        'task': {
            'goal': 'Produce a polished, source-grounded final answer and a short list of contextual follow-up suggestions.',
            'output_contract': {
                'answer_text': 'string',
                'followup_suggestions': ['string'],
                'style_applied': 'string',
            },
            'quality_bar': {
                'meaning_first': True,
                'source_boundaries_explicit': True,
                'no_pipeline_jargon': True,
                'short_surah_explanations_should_sound_natural': True,
            },
        },
    }
    return json.dumps(payload, ensure_ascii=False)
