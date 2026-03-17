-- Canonical Quran units
CREATE TABLE IF NOT EXISTS quran_ayahs (
    id SERIAL PRIMARY KEY,
    source_id TEXT NOT NULL,
    surah_no INT NOT NULL,
    ayah_no INT NOT NULL,
    surah_name_ar TEXT,
    language TEXT NOT NULL,
    text_display TEXT NOT NULL,
    text_normalized TEXT,
    bismillah TEXT,
    translation_name TEXT,
    canonical_source_id TEXT NOT NULL UNIQUE,
    citation_string TEXT NOT NULL
);
