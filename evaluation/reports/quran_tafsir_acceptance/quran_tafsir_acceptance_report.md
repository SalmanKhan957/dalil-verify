# Acceptance Report — quran-tafsir-explain-v1

- Total cases: 27
- Passed cases: 6
- Failed cases: 21
- Overall pass rate: 22.2%
- All gates passed: no

## Metrics

- Quran resolution rate: 100.0%
- Tafsir inclusion rate: 0.0%
- Citation presence rate: 100.0%
- Abstention rate: 100.0%
- Unexpected error rate: 74.1%

## Gates

- quran_resolution_gate: PASS
- tafsir_inclusion_gate: FAIL
- citation_presence_gate: PASS
- abstention_gate: PASS
- unexpected_error_gate: FAIL
- overall_pass_gate: FAIL

## Failed Cases

- `surah_fatiha_explain` — Explain Surah Al-Fatiha — tafsir_included, unexpected_error
- `surah_ikhlas_explain` — Explain Surah Al-Ikhlas — tafsir_included, unexpected_error, answer_quality
- `surah_asr_explain` — Explain Surah Al-Asr — tafsir_included, unexpected_error, answer_quality
- `surah_kawthar_explain` — Explain Surah Al-Kawthar — tafsir_included, unexpected_error, answer_quality
- `surah_nas_explain` — Explain Surah An-Nas — tafsir_included, unexpected_error
- `surah_falaq_explain` — Explain Surah Al-Falaq — tafsir_included, unexpected_error
- `surah_masad_explain` — Explain Surah Al-Masad — tafsir_included, unexpected_error
- `surah_fil_explain` — Explain Surah Al-Fil — tafsir_included, unexpected_error
- `surah_fatiha_tafsir` — Tafsir of Surah Al-Fatiha — tafsir_included, unexpected_error
- `surah_ikhlas_tafsir` — Tafsir of Surah Ikhlas — tafsir_included, unexpected_error, answer_quality
- `ayah_255_tafsir` — Explain 2:255 with tafsir — tafsir_included, unexpected_error
- `ibn_kathir_ikhlas` — Ibn Kathir on Surah Al-Ikhlas — tafsir_included, unexpected_error, answer_quality
- `ayah_255_explain` — Explain 2:255 — tafsir_included, unexpected_error
- `ayah_94_5_6_explain` — Meaning of 94:5-6 — tafsir_included, unexpected_error, answer_quality
- `ayah_112_1_4_explain` — Explain 112:1-4 — tafsir_included, unexpected_error, answer_quality
- `ayah_103_1_3_explain` — Explain 103:1-3 — tafsir_included, unexpected_error, answer_quality
- `ayah_108_1_3_explain` — Explain 108:1-3 — tafsir_included, unexpected_error, answer_quality
- `ayah_111_1_5_explain` — Explain 111:1-5 — tafsir_included, unexpected_error
- `ayah_114_1_6_explain` — Explain 114:1-6 — tafsir_included, unexpected_error
- `ayah_113_1_5_explain` — Explain 113:1-5 — tafsir_included, unexpected_error
- `ikhlas_quran_only` — Explain Surah Al-Ikhlas — answer_quality
