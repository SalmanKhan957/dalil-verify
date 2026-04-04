from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranslationWork:
    source_id: str
    display_name: str
