# Bukhari enrichment report — v1

Total enriched records: **7272**
Abstained (no primary topic): **240** (3.3%)

Topic density distribution (non-abstain):
- min=0.00  p25=0.80  median=0.90  p75=0.90  max=1.00

## Top 30 topics by record count
- `ritual.salah.prayer_general` — **335** — Prayer (salah) — general rulings and virtues
- `quran.tafsir.general` — **320** — Prophetic commentary on the Qur'an — general tafsir
- `historical.maghazi.general` — **201** — Military expeditions — general and minor campaigns
- `historical.prophet_biography.merits` — **176** — Virtues and merits of the Prophet ﷺ
- `fiqh.business.sales_general` — **169** — Sales and trade — general rulings
- `ritual.hajj.general` — **140** — Hajj — general rulings and virtues
- `aqeedah.tawhid.general` — **127** — Tawhid — the oneness of Allah
- `historical.jihad.general_etiquette` — **126** — Jihad — general rulings and etiquette
- `fiqh.nikah.marriage_general` — **121** — Marriage — general rulings and conduct
- `historical.ansar_muhajireen` — **115** — Merits of the Ansar and the Muhajireen
- `fiqh.food.food_general` — **113** — Food and eating — permissibility and etiquette
- `fiqh.business.gifts_hiba` — **112** — Gifts and giving (hiba)
- `ritual.tahara.wudu_ablution` — **102** — Wudu (ablution) — procedure, invalidators, virtues
- `fiqh.dress.general_dress` — **101** — Dress — general rulings (non-specialised)
- `ritual.sawm.fasting_general` — **101** — Fasting — general rulings and virtues
- `quran.virtues.recitation` — **100** — Virtues of Qur'an recitation
- `akhlaq.dua.invocations_general` — **99** — Invocations and du'a — general
- `fiqh.hudood.zina_adultery` — **91** — Hudud of zina — illegal sexual intercourse and its punishment
- `eschatology.paradise_jannah` — **87** — Paradise (jannah) and its blessings
- `historical.jihad.conduct_rules` — **83** — Conduct in battle and treatment of the enemy
- `eschatology.end_times_general` — **81** — End-times afflictions and fitan
- `fiqh.food.hunting_slaughter` — **74** — Hunting, slaughter and permissible game
- `historical.maghazi.badr` — **73** — The Battle of Badr
- `fiqh.business.manumission` — **73** — Manumission and emancipation of slaves
- `historical.companions.others` — **73** — Other companions and families
- `fiqh.justice.judgments_ahkam` — **72** — Judgments, pledges of allegiance and governance (ahkam)
- `ritual.salah.times_of_prayer` — **69** — Times of the five daily prayers
- `historical.prophets.other` — **68** — Other prophets — Yusuf, Ayub, Dawud, Sulayman, Yunus etc.
- `akhlaq.riqaq.heart_tender_general` — **65** — General spiritual reminders (riqaq)
- `akhlaq.adab.truthfulness_lying` — **64** — Truthfulness and the prohibition of lying

## Under-populated topics (<5 records): 14
- `ritual.sawm.voluntary_fasts` — 1
- `historical.prophets.nuh_flood` — 1
- `akhlaq.dua.morning_evening_adhkar` — 1
- `aqeedah.fitrah_innate_faith` — 2
- `akhlaq.adab.envy_hasad` — 2
- `akhlaq.adab.backbiting_ghayba` — 2
- `akhlaq.dua.istighfar_tawbah` — 2
- `ritual.hajj.sacred_mosque_kaba` — 3
- `ritual.sawm.travel_sick_fasting` — 3
- `fiqh.business.guarantee_kafala` — 3
- `akhlaq.adab.mocking_nicknames` — 3
- `fiqh.nikah.ila_vow_abstinence` — 4
- `eschatology.mahdi_isa_return` — 4
- `aqeedah.jinn_satan` — 4

## Unused taxonomy slugs: 3
- `akhlaq.dua.dhikr_tasbih`
- `aqeedah.iman_increase_decrease`
- `eschatology.bridge_mizan`

## Canonical test-case coverage
- **zina**: 91 records → slugs ['fiqh.hudood.zina_adultery']
- **dajjal**: 36 records → slugs ['eschatology.dajjal']
- **riba/usury**: 32 records → slugs ['fiqh.business.riba_usury']
- **backbiting**: 2 records → slugs ['akhlaq.adab.backbiting_ghayba']
- **anger**: 43 records → slugs ['akhlaq.adab.anger_control']
- **intention/niyya**: 10 records → slugs ['foundational.intention_niyya']
- **prayer times**: 69 records → slugs ['ritual.salah.times_of_prayer']
- **patience**: 14 records → slugs ['akhlaq.adab.patience_sabr']
- **theft**: 28 records → slugs ['fiqh.hudood.theft_sariqa']
- **paradise**: 87 records → slugs ['eschatology.paradise_jannah']