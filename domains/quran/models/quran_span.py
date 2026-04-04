from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QuranSpan:
    surah_no: int
    ayah_start: int
    ayah_end: int

    def ref(self) -> str:
        return f'{self.surah_no}:{self.ayah_start}-{self.ayah_end}'
