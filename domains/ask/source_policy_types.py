from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class QuranSourcePolicyDecision:
    domain: str = 'quran'
    allowed: bool = True
    included: bool = True
    policy_reason: str | None = None
    selected_capability: str | None = None
    available_capabilities: list[str] = field(default_factory=list)
    requested_text_source_id: str | None = None
    requested_translation_source_id: str | None = None
    selected_text_source_id: str | None = None
    selected_translation_source_id: str | None = None
    text_source_origin: str | None = None
    translation_source_origin: str | None = None


@dataclass(slots=True)
class TafsirSourcePolicyDecision:
    domain: str = 'tafsir'
    selected_capability: str | None = None
    available_capabilities: list[str] = field(default_factory=list)
    requested: bool = False
    request_origin: str | None = None
    requested_source_id: str | None = None
    selected_source_id: str | None = None
    request_mode: str = 'auto'
    mode_enforced: bool = False
    allowed: bool = False
    included: bool = False
    policy_reason: str | None = None


@dataclass(slots=True)
class HadithSourcePolicyDecision:
    domain: str = 'hadith'
    selected_capability: str | None = None
    available_capabilities: list[str] = field(default_factory=list)
    requested: bool = False
    request_origin: str | None = None
    requested_source_id: str | None = None
    selected_source_id: str | None = None
    request_mode: str = 'auto'
    mode_enforced: bool = False
    allowed: bool = False
    included: bool = False
    approved_for_answering: bool = False
    answer_capability: str | None = None
    policy_reason: str | None = None


@dataclass(slots=True)
class AskSourcePolicyDecision:
    quran: QuranSourcePolicyDecision
    tafsir: TafsirSourcePolicyDecision
    hadith: HadithSourcePolicyDecision | None = None
