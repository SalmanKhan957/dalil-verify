# PROJECT_HANDOFF.md
## Dalil Verify — Quran Verifier + Ask Engine Planning Handoff

## 1. Project Summary

**Project name:** Dalil Verify  
**Current phase:** Quran-first verifier MVP  
**Primary goal:** Build a **high-trust, citation-first Islamic verification and retrieval product**.  
**Current scope:** **Arabic Quran verifier** with **ayah lane + passage lane fusion**.  
**Planned future scope:** Ask engine for **English Quran lookup**, later **hadith**, later possibly **tafsir**.

This project is deliberately **not** being built as a generic “Islamic chatbot.”  
The strategic decision is:

- **Verifier first**
- **Bounded ask engine second**
- **No fatwa engine**
- **No scholar replacement**
- **No open-ended religious authority behavior**

The product is meant to be:
- **source-grounded**
- **citation-first**
- **careful with wording**
- **explicit about limits**

---

## 2. Product Decisions Already Made

### 2.1 Verifier scope
For now, the verifier is focused on:

- **Arabic Quran input**
- exact or close verification against Quran text
- support for:
  - **single ayah**
  - **multi-ayah pasted excerpts**
  - normalization variants
  - passage support via derived windows

### 2.2 Ask engine scope
The ask engine is the planned place for:

- **English / translated Quran queries**
- “Where does it say…”
- “Show the verse about…”
- later, **hadith retrieval**
- later, **tafsir lookup**
- later, broader source-grounded search

### 2.3 Important strategic split
The current working product split is:

- **Arabic Quran verifier** → strict, high-precision, citation-first
- **English / translated / paraphrased lookup** → ask engine / retrieval engine

This avoids forcing English translations into verifier semantics where wording differences across translations can create false certainty.

### 2.4 What the product is not
The project is **not**:

- a fatwa engine
- a scholar replacement
- a sect-comparison bot
- a general “ask Islam anything” chatbot
- a system that should present itself as theological authority

---

## 3. Current Technical Status

### 3.1 Quran Arabic canonical dataset
Built from **Tanzil XML** into canonical ayah rows.

Current canonical dataset includes:
- `source_id`
- `source_type`
- `language`
- `translation_name`
- `surah_no`
- `ayah_no`
- `surah_name_ar`
- `text_display`
- `text_normalized_light`
- `text_normalized_aggressive`
- `bismillah`
- `canonical_source_id`
- `citation_string`

### 3.2 Passage dataset
Derived Quran passage windows are generated.

Currently supported passage window sizes:
- **2 ayah**
- **3 ayah**
- **4 ayah**

Canonical source model is still:
- **1 ayah = truth unit**

Passage windows are a **derived retrieval layer**, not canonical truth.

### 3.3 Retrieval lanes
Two retrieval lanes exist:

#### Ayah lane
Used for:
- single ayah
- verse fragments
- precision-first matching

#### Passage lane
Used for:
- adjacent multi-ayah excerpts
- longer pasted Quran passages
- combined ayat from forwards / sermons / social media posts

### 3.4 Fusion logic
A fusion/comparator layer exists that runs both lanes and chooses the preferred result.

Current outputs include:
- **preferred lane**
- **rationale**
- **ayah result**
- **passage result**
- **secondary result**

### 3.5 API
FastAPI endpoint exists:

- `POST /verify/quran`

Current production-style response shape is cleaner than the earlier debug-heavy shape:
- `query`
- `preferred_lane`
- `match_status`
- `confidence`
- `boundary_note`
- `best_match`
- `also_related`
- optional `debug`

### 3.6 Logging
Structured JSONL logs exist.

Current log captures include:
- request id
- client IP
- query
- query char count
- query token count
- preferred lane
- decision rule
- rationale
- match status
- confidence
- preferred citation
- ayah lane analytics
- passage lane analytics
- score delta between lanes
- debug flag

### 3.7 Tests
Pytest API test suite is green.

Current status:
- **7 passing tests**

### 3.8 Evaluation
Three layers of evaluation have been built:

#### Quran ayah verifier evaluation
Covers:
- exact ayat
- fragments
- normalization cases
- ask-like routing
- cannot-assess behavior

#### Quran passage evaluation
Covers:
- 2-ayah passages
- 3-ayah passages
- mixed single-vs-passage cases
- longer future-scope cases

#### Fusion evaluation
The fusion behavior is tested indirectly through passage suite and API tests.

Current state:
- **core ayah scope green**
- **core passage scope green**
- **future longer-passage cases improved after 4-ayah windows**

---

## 4. Current Retrieval / Matching Logic

### 4.1 Current verifier is a prototype matcher
The current verifier is **correct enough for prototyping** but **not performant enough for scale**.

It currently relies on:
- normalized text
- brute-force candidate scoring
- RapidFuzz scoring
- heuristic lane fusion

This is acceptable for prototyping and not acceptable for real production latency.

### 4.2 Light normalization
Used for primary precision.

Examples include:
- strip diacritics
- normalize hamza forms
- normalize whitespace
- preserve precision

### 4.3 Aggressive normalization
Used as fallback / rescue normalization.

Examples include:
- additional Arabic character collapsing
- punctuation stripping
- Quranic mark stripping
- more recall-oriented behavior

### 4.4 Match statuses
Core statuses currently used:
- **Exact match found**
- **Close / partial match found**
- **No reliable match found in current corpus**
- **Cannot assess**

### 4.5 Fusion decision
Fusion currently uses:
- match-status rank
- score comparison
- query token count
- whether a single ayah already cleanly contains the query
- whether the passage spans multiple ayat
- default precision bias toward ayah lane

This fusion is **heuristic**, not infallible.  
It is, however, **deterministic, inspectable, logged, and testable**.

---

## 5. Important Performance Status

### 5.1 Current problem
Latency is currently too high for some longer queries.

Observed issue:
- a **4-ayah** passage query took **30+ seconds** in prototype flow

### 5.2 Why this is happening
Current prototype flow still does expensive scoring over too many candidates:
- ayah lane
- passage lane
- multiple fuzzy scores per row
- then fusion

### 5.3 Current conclusion
Correctness is now strong enough to move on.  
**Latency is the next engineering bottleneck.**

---

## 6. Recommended Retrieval Direction Going Forward

### 6.1 For verifier
Recommended strategy:

- **lexical shortlist first**
- **fuzzy rerank second**
- **fusion third**

Not:
- vector-first verifier
- brute-force fuzzy over entire corpus
- LLM-first matching

### 6.2 Best likely near-term implementation
For the verifier, the strongest next technical direction is:

- token inverted index or full-text shortlist
- candidate pruning
- run fuzzy scoring only on shortlist
- then lane fusion

### 6.3 Ask engine direction
The ask engine should later handle:
- English Quran queries
- translated wording
- “Where does it say…”
- hadith source lookup
- semantic and paraphrase retrieval

The ask engine is expected to use a broader retrieval stack than the verifier.

---

## 7. Current Position on English Quran

### 7.1 Important decision already made
At this stage, the project is **not** forcing English Quran into verifier semantics.

Rationale:
- translation wording varies
- user pasted wording may come from a different translation
- exactness claims become unsafe quickly

### 7.2 Current stance
- **Arabic Quran verifier** is enough for verifier MVP
- **English Quran retrieval** should live inside the ask engine

---

## 8. Quran.Foundation Access Status

### 8.1 Access obtained
Quran.Foundation API access has been obtained.

### 8.2 Important note
**The client secret was pasted into chat and should be treated as exposed.**
Action required:
- **rotate the production secret**
- move all credentials into server-side environment variables only

### 8.3 Intended use
Current intent is to use Quran.Foundation for:
- content access
- The Clear Quran access path
- future ask engine support

### 8.4 Constraint
For English content, the design must respect Quran.Foundation terms, including:
- API-backed content access
- caution around long-term storage/caching
- caution around translation handling

---

## 9. Dynamic Grouping — Concept Not Yet Implemented

### 9.1 What it is
Dynamic adjacent-hit grouping means:

1. retrieve top ayah hits
2. detect adjacent ayat in same surah
3. merge them dynamically into a passage candidate
4. compare that candidate with fixed windows

### 9.2 Why it matters
It may become preferable to:
- fixed windows up to very large sizes
- endless precomputation of overlapping windows
- index bloat for long passages

### 9.3 Current status
**Not implemented yet.**
Current decision:
- **delay dynamic grouping for now**
- use **2/3/4 fixed windows**
- revisit dynamic grouping only if logs show repeated need for longer excerpts

---

## 10. Current Decision on Window Sizes

### 10.1 Current implemented sizes
- **2**
- **3**
- **4**

### 10.2 Strategic decision
Do **not** immediately expand fixed windows to 10.

Reason:
- more overlap
- more retrieval noise
- more ranking ambiguity
- less crisp citations

### 10.3 Current recommendation
Stay with:
- **2/3/4 fixed windows**
- gather lane analytics from real queries
- revisit larger windows only if the logs justify it

---

## 11. Known Warnings / Cleanup Items

### 11.1 FastAPI startup warning
There is currently a warning that `@app.on_event("startup")` is deprecated.

Recommended later cleanup:
- move to **lifespan** handlers

This is **not currently breaking functionality**.

---

## 12. File / Module Map

### Core data + ingestion
- `scripts/ingestion/parse_quran_xml.py`
- `scripts/ingestion/generate_quran_passage_windows.py`

### Shared normalization
- `scripts/common/text_normalization.py`

### Ayah verifier
- `scripts/evaluation/quran_verifier_baseline.py`

### Passage verifier
- `scripts/evaluation/quran_passage_verifier_baseline.py`

### Fusion comparator
- `scripts/evaluation/compare_quran_ayah_vs_passage.py`

### Evaluation runners
- `scripts/evaluation/run_quran_gold_tests_v3.py`
- `scripts/evaluation/run_quran_passage_gold_tests_v1.py`
- `scripts/evaluation/summarize_quran_lane_logs.py`

### API
- `apps/api/main.py`
- `apps/api/schemas.py`
- `apps/api/logging_utils.py`

### Tests
- `tests/test_api.py`

### Processed datasets
- `data/processed/quran/quran_arabic_canonical.csv`
- `data/processed/quran/quran_arabic_canonical.jsonl`
- `data/processed/quran_passages/quran_passage_windows_v1.csv`
- `data/processed/quran_passages/quran_passage_windows_v1.jsonl`

### Evaluation outputs
- `data/processed/evaluation/...`

### Logs
- `logs/verify_quran.jsonl`

---

## 13. Current Test / Evaluation State

### API tests
- **7 passed**

### Quran ayah core scope
- **green**

### Passage core scope
- **green**

### Future longer-passage scope
- improved after adding **4-ayah windows**
- still intentionally separate from core KPI decisions

### Current interpretation
The Quran verifier is now:
- **technically credible**
- **well structured**
- **still narrow**
- **not yet performance-optimized**

---

## 14. Immediate Next Priorities

### Priority 1 — retrieval performance
Optimize verifier speed:
- shortlist candidates first
- fuzzy rerank second
- avoid full brute-force scoring across whole datasets

### Priority 2 — ask engine retrieval strategy
Design the ask engine retrieval stack for:
- English Quran lookup
- translated wording
- later hadith
- source-grounded answer assembly

### Priority 3 — environment / security cleanup
- rotate exposed Quran.Foundation secret
- move secrets to `.env`
- ensure no credentials are committed anywhere

### Priority 4 — optional cleanup
- replace deprecated FastAPI startup handler with lifespan

---

## 15. Questions the Next Engineer / Assistant Should Solve

1. **What is the best retrieval architecture for the ask engine**, given:
   - Arabic Quran verifier already exists
   - English Quran lookup belongs in ask engine
   - later hadith and tafsir may be added

2. **What is the best fast retrieval design for verifier**, replacing current brute-force fuzzy scoring?

3. **Should the ask engine use lexical + semantic hybrid retrieval**, and if so, how should corpora be separated?

4. **How should hadith corpora be structured for retrieval?**
   - canonical unit
   - metadata
   - duplicate narration handling
   - Arabic vs English storage

5. **How should answer generation be bounded** so it remains source-grounded and avoids overclaiming?

---

## 16. Product Guardrails to Preserve

Any future work should preserve these:

- **citation-first behavior**
- **clear source boundaries**
- **no fatwa authority**
- **no scholar replacement framing**
- **Arabic verifier stays high precision**
- **English / translated lookup handled carefully**
- **tests and logs remain first-class**
- **truth over convenience**

---

## 17. One-Line Summary

**Dalil Verify currently has a fused Arabic Quran verifier with ayah and passage support, strong core evaluation, working API/tests/logging, and now needs retrieval optimization plus a well-designed ask engine strategy for English Quran and later hadith.**