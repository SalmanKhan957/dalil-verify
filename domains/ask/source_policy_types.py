from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QuranSourcePolicyDecision:
    domain: str = 'quran'
    allowed: bool = True
    included: bool = True
    policy_reason: str | None = None
    requested_text_source_id: str | None = None
    requested_translation_source_id: str | None = None
    selected_text_source_id: str | None = None
    selected_translation_source_id: str | None = None
    text_source_origin: str | None = None
    translation_source_origin: str | None = None


@dataclass(slots=True)
class TafsirSourcePolicyDecision:
    domain: str = 'tafsir'
    requested: bool = False
    request_origin: str | None = None
    requested_source_id: str | None = None
    selected_source_id: str | None = None
    allowed: bool = False
    included: bool = False
    policy_reason: str | None = None


@dataclass(slots=True)
class AskSourcePolicyDecision:
    quran: QuranSourcePolicyDecision
    tafsir: TafsirSourcePolicyDecision
