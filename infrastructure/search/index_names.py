TAFSIR_INDEX = "dalil-tafsir"
HADITH_INDEX = "dalil-hadith"
HADITH_TOPICAL_INDEX = "dalil-hadith-topical-v2"
HADITH_GUIDANCE_UNIT_INDEX = "dalil-hadith-guidance-units-v1"

# Bukhari hybrid topical index — hybrid BM25 + kNN over raw Bukhari hadith.
# v1 (legacy): BM25 on raw matn_text + synthetic_baab_label, dirty embeddings.
# v2: primary_topics / secondary_topics / concept_vocabulary / matn_text_clean
#     as first-class fields, narrator removed from searchable set, embeddings
#     regenerated against clean text.
# Runtime reads via the alias HADITH_BUKHARI_TOPICAL_INDEX so cutover is atomic.
HADITH_BUKHARI_TOPICAL_INDEX_V1 = "dalil-hadith-bukhari-topical-v1"
HADITH_BUKHARI_TOPICAL_INDEX_V2 = "dalil-hadith-bukhari-topical-v2"
HADITH_BUKHARI_TOPICAL_ALIAS = "dalil-hadith-bukhari-topical"

# Default (what runtime code should import). Points at the alias so index
# swaps happen without code changes.
HADITH_BUKHARI_TOPICAL_INDEX = HADITH_BUKHARI_TOPICAL_ALIAS
