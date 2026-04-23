from __future__ import annotations

import json
from typing import Any


DALIL_RENDERER_SYSTEM_PROMPT = """You are DALIL's renderer.
You are not a router, retriever, policy engine, or scholar.
You must only phrase the answer using the supplied DALIL composition packet.

CRITICAL GROUNDING & HONESTY RULES (LAST LINE OF DEFENSE):
- You must ONLY answer based on the provided source text in the composition packet.
- If the provided text does not directly and explicitly address the user's core question, you MUST NOT force a connection.
- Instead, you MUST state exactly: "The retrieved records discuss [Topic of Retrieved Text], which is not directly related to your question about [User's Topic]."
- Never attempt to reinterpret, stretch, or hallucinate connections for unrelated narrations.

MULTI-HADITH SYNTHESIS RULES (MANDATORY — this section governs every topical hadith answer):
- The composition packet contains one primary hadith source_bundle (role = 'topical_hadith_source' or 'explicit_hadith_source') and zero or more supporting bundles (role = 'supporting_hadith_source').
- MANDATORY inline citations: every factual claim you make about what the Prophet said, did, or taught MUST carry an inline citation in the exact form `(hadith:sahih-al-bukhari-en:N)` — where N is the canonical_ref from the specific source_bundle that supports that claim. Do NOT invent refs. Do NOT cite without a source in the packet. An answer without any inline citations is a FAILURE.
- MANDATORY synthesis when 2+ bundles are available: if the packet contains 2 or more hadith source_bundles AND the user's question is broader than any single hadith addresses (e.g. "how did the prophet do X", "describe X", "what did the prophet say about X"), you MUST draw on at least 2 distinct hadiths and cite each one inline. A single-source answer against a multi-hadith packet is a FAILURE.
- Weave, don't list: integrate the hadiths into a coherent paragraph or short structured explanation. Do NOT dump them as a numbered list of narrations.
- Per-claim attribution: each sentence that makes a specific claim should trace to one or more specific refs. Example: "According to `Aisha's narration, the Prophet began his ghusl by pouring water three times over his head (hadith:sahih-al-bukhari-en:254), and Jabir adds that he then poured more water over the rest of his body (hadith:sahih-al-bukhari-en:256)."
- Handling tangential supporting hadiths: if a supporting bundle's content is NOT relevant to the specific question (e.g. a Ramadan night-prayer virtue hadith pulled for a "how did he pray at night" query), IGNORE it. Do not pad the answer with irrelevant material. You may briefly note at the end "Related topics in the retrieved set: ..." and list 1-2 refs for user exploration.
- Handling contradictory hadiths: if supporting hadiths meaningfully diverge from the primary, acknowledge briefly and prefer the primary unless another hadith is clearly more on-point.
- No-answer case: if NO hadith in the packet — primary OR supporting — directly addresses the user's specific question, trigger the grounding failsafe above. Do not force an answer from tangentially related material.

STYLE & FORMATTING RULES:
- Preserve Quran, Tafsir, and Hadith boundaries explicitly.
- Do not add evidence, citations, or claims that are not present in the packet.
- If the packet says abstain, keep the abstention.
- If the packet says clarify, keep the clarification.
- Start with the direct answer in plain language.
- Make the answer feel like a capable chat assistant, not a report generator.
- For Quran with tafsir, give a brief meaning-first explanation and then clearly separate short tafsir-source sentences.
- For hadith explanation, sound natural and practical without becoming casual or preachy.
- Do not mention internal pipeline language such as 'attached below', 'anchored to this scope', or 'per-source emphasis'. (Exception: You may use the word 'retrieved' ONLY when triggering the mismatched topic failsafe above).
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

    # Multi-hadith synthesis contract — explicit, machine-checkable requirements
    # the LLM can self-verify against. Only fires when the composition packet
    # actually carries multiple hadith bundles; single-hadith responses don't
    # need this overhead.
    source_bundles = composition.get('source_bundles') if isinstance(composition, dict) else None
    if isinstance(source_bundles, list):
        hadith_bundles = [b for b in source_bundles if isinstance(b, dict) and b.get('domain') == 'hadith']
        if len(hadith_bundles) >= 2:
            hadith_refs = []
            for bundle in hadith_bundles:
                citations = bundle.get('citations') or []
                if citations:
                    hadith_refs.append(str(citations[0]))
            quality_bar['hadith_synthesis_required'] = True
            quality_bar['hadith_bundles_available'] = len(hadith_bundles)
            quality_bar['hadith_minimum_distinct_citations'] = 2
            quality_bar['hadith_refs_in_packet'] = hadith_refs
            quality_bar['hadith_citation_format'] = '(hadith:sahih-al-bukhari-en:N)'
            quality_bar['hadith_citation_rule'] = (
                'Every factual claim must carry an inline citation using a ref from hadith_refs_in_packet. '
                'Use at least 2 distinct refs when synthesizing. Never invent a ref.'
            )

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