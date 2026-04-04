from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VerseKey:
    surah_no: int
    ayah_no: int

    def __str__(self) -> str:
        return f'{self.surah_no}:{self.ayah_no}'
