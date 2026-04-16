# DALIL Product Handoff — Updated v25 (Pre-Full-MVP-Test)
## Current bounded MVP productionization tranches have been implemented in patch form, but the full integrated MVP test pack has **not** yet been run end to end after the latest tranche sequence. Treat current state as **production-closer and heavily prepared**, not yet finally certified.

This handoff supersedes earlier DALIL handoffs for continuity of context.

The most important update is this:

**DALIL has now moved beyond the earlier “green bounded MVP with known next sequence” framing into a new pre-certification state:**
- the original bounded public MVP truth still holds conceptually
- the repo has received a full productionization tranche sequence for the current bounded MVP surface
- however, the user has **not yet run the full integrated MVP verification pack after the latest tranche series**
- therefore, no next chat should casually claim the current repo is finally production-certified until the full MVP pack is run and reviewed

That distinction must be preserved accurately.

---

# 1) Core product intent

DALIL is being built as a **source-driven Islamic chatbot** for a **large-scale community**.

Long-term, it is intended to support:
- explicit Quran references
- Arabic Quran quote verification
- Quran explanation
- Quran + Tafsir answers
- Hadith retrieval and explanation
- governed source-driven topical Islamic questions
- conversational follow-ups
- later source-grounded continuation across long-form reading sessions
- bounded model-assisted phrasing/rendering downstream of DALIL-owned truth

DALIL is **not** supposed to remain just:
- a verifier
- a citation parser
- a narrow explicit-reference explainer
- a bounded explicit Hadith lookup utility
- a topical utility without real conversational discipline
- a stitched one-shot answer surface for very large Quran/Tafsir asks

Those are foundation layers, not the end product.

The real target product remains:
- an **Ask-first, source-driven Islamic chatbot**
- grounded in approved sources
- with strict source boundaries and trust behavior
- governed for correctness, abstention, and capability restrictions
- architected for operational reliability and later controlled expansion

---

# 2) Current public MVP boundary — preserve this truth

The current bounded public MVP is still intentionally narrower than the eventual product.

The current bounded release boundary is:
- explicit Quran
- Quran + Tafsir
- Arabic Quran quote verification
- explicit Hadith lookup/explain
- query normalization for supported asks
- bounded chat-style rendering
- bounded anchored follow-up / continuity support

The current bounded release boundary is **not**:
- public topical Hadith
- broad topical Islamic Q&A
- mixed-source public topical answering
- persistent open-ended memory
- generic broad Islamic chat
- LLM-led routing or source selection

That product boundary must still be preserved.

---

# 3) What changed since v24

The most important change since v24 is **not** a widening of the product boundary.

It is that a full **productionization tranche sequence** has now been prepared and delivered for the current bounded MVP surface.

## Delivered tranche sequence (implemented in patch form)

### Tranche 0 — Empty-evidence trust hardening
Purpose:
- hard no-answer posture when evidence is empty or insufficient
- prevent renderer improvisation on weak evidence
- central evidence-readiness contract

Primary files changed in this tranche:
- `domains/answer_engine/composition_builder.py`
- `domains/answer_engine/conversational_renderer.py`
- `domains/answer_engine/response_builder.py`
- `domains/answer_engine/evidence_readiness.py`
- `domains/conversation/followup_capabilities.py`

### Tranche 1 — Hosted query normalization
Purpose:
- bounded hosted cleanup before deterministic classification
- no delegation of routing, policy, source selection, or abstention
- deterministic fallback when hosted normalization fails or is rejected

Primary files changed in this tranche:
- `infrastructure/config/settings.py`
- `infrastructure/clients/openai_query_normalizer.py`
- `domains/query_intelligence/models.py`
- `domains/query_intelligence/hosted_normalization.py`
- `domains/ask/classifier.py`
- `domains/ask/dispatcher.py`
- `tests/unit/test_hosted_query_normalization.py`

### Tranche 1.1 — Hosted normalization fallback observability patch
Purpose:
- expose whether hosted normalization was attempted
- expose fallback reason/error class instead of silently flattening everything into deterministic output

Primary files changed in this tranche:
- `domains/query_intelligence/models.py`
- `domains/query_intelligence/hosted_normalization.py`
- `infrastructure/clients/openai_query_normalizer.py`
- `tests/unit/test_hosted_query_normalization.py`

### Tranche 2 — Retrieval hygiene and routing guardrails
Purpose:
- stronger deterministic normalization
- better transliteration and compact-form handling
- data-driven family guardrails
- prevent tafsir-source + surah asks from drifting into the wrong family
- prevent stale anchor/session state from hijacking clearly fresh scoped asks

Primary files changed in this tranche:
- `domains/query_intelligence/normalization.py`
- `domains/query_intelligence/models.py`
- `domains/query_intelligence/catalog.py`
- `domains/query_intelligence/query_family_classifier.py`
- `domains/ask/topical_query.py`
- `domains/ask/classifier.py`
- `assets/query_intelligence/query_families.v1.json`
- routing/normalization tests

### Tranche 2.1 — Compatibility import fix
Purpose:
- restore normalization helper exports needed by existing `concept_linker.py` imports after tranche integration

Primary file changed:
- `domains/query_intelligence/normalization.py`

### Tranche 3 — Observability / flags / contract lock
Purpose:
- request-level observability
- canonical public response surface discipline
- feature flags for legacy result/debug posture
- response header request id

Primary files changed in this tranche:
- `infrastructure/config/settings.py`
- `domains/ask/observability.py`
- `domains/ask/dispatcher.py`
- `domains/ask/response_surface.py`
- `apps/ask_api/routes/ask.py`
- `apps/ask_api/routes/explain.py`
- observability/contract tests

### Tranche 4 — Productionize current bounded continuity substrate
Purpose:
- keep current bounded continuity behavior
- add production-realistic backend model for anchor/session state
- support memory, sqlite, and redis backends
- add TTL-based expiry
- add safe redis→sqlite fallback

Primary files changed in this tranche:
- `infrastructure/config/settings.py`
- `infrastructure/cache/keys.py`
- `infrastructure/cache/redis_client.py`
- `domains/conversation/anchor_store.py`
- `domains/ask/observability.py`
- backend tests

### Tranche 5 — Final production lock
Purpose:
- release posture discipline
- startup validation
- reject obviously invalid production configs
- health posture surfacing

Primary files changed in this tranche:
- `infrastructure/config/settings.py`
- `infrastructure/config/release_lock.py`
- `domains/quran/verifier/bootstrap.py`
- `domains/quran/verifier/service.py`
- `apps/ask_api/routes/health.py`
- `domains/ask/observability.py`
- release-lock tests

### Additional utility delivered
A **manual bounded MVP test runner** in PowerShell has also been prepared so the user can run one command and produce:
- raw per-case JSON
- a summary JSON
- a summary Markdown report

---

# 4) Critical testing status — do not misstate this

This is the most important operational truth to preserve in the next chat.

## What is true
Before the productionization tranche sequence, the repo had a green bounded public acceptance wall for the earlier bounded MVP surface:
- MVP acceptance = pass
- Quran/Tafsir acceptance = pass
- ask-conversation acceptance = pass

## What is also true now
The repo has since received the productionization tranche sequence above, and selected targeted unit/regression slices were reported passing during tranche delivery.

## What is **not yet true**
The user has **not yet run the full integrated MVP verification pack after the latest tranche sequence**.

That means the correct current status is:

**DALIL is production-closer for the bounded MVP surface, but full integrated post-tranche MVP certification is still pending.**

Do not allow a later chat to casually state that the current repo is fully production-certified unless the user has actually run the full MVP pack and reviewed the failures/suspicious cases.

---

# 5) Accurate current continuity truth

The older continuity framing must still be corrected carefully.

## What is true
Bounded continuity is more than structural. It is materially live in `/ask`.

The repo includes conversation-state modules such as:
- `session_state.py`
- `state_hydrator.py`
- `followup_capabilities.py`
- `followup_resolver.py`
- `followup_phrasebook.py`
- anchor/session store infrastructure

Supported bounded behaviors include:
- `anchored_followup_quran`
- `anchored_followup_tafsir`
- `anchored_followup_hadith`
- `repeat_exact_text`
- `simplify`
- `focus_source`
- `summarize_hadith`
- `extract_hadith_lesson`
- bounded relative Quran next/previous navigation where supported

## What is not yet safe to claim
DALIL still does **not** yet have a full product-grade long-form continuation layer.

What remains missing for that later milestone includes:
- first-class continuation intent
- cursor / position model for long answers
- source-scoped continuation semantics such as `continue Ibn Kathir`
- open exposition session state
- broader conversation-scale intent normalization
- journey-level regression coverage for long-form reading flows

## Accurate continuity statement
The correct statement remains:

**bounded continuity is live and materially healthier in `/ask`, but DALIL still does not yet have a full source-grounded continuation layer for long-form conversational reading and explanation.**

---

# 6) Hosted model direction — preserve strict governance

Hosted model usage is now explicitly present in the repo for **query normalization** and may also be used for rendering depending on deployment/config choice.

The correct governance boundary remains:

## Allowed hosted use
- pre-classifier query cleanup / normalization
- bounded renderer phrasing downstream of DALIL-owned evidence and policy
- later semantic intent normalization into DALIL-owned typed intents, if explicitly chosen

## Not allowed hosted use
- routing sovereignty
- source selection
- policy decisions
- evidence gating
- abstention decisions
- continuation position/cursor control

The hosted model must remain:
- feature-flagged
- bounded
- replaceable
- subordinate to DALIL-owned control plane truth

---

# 7) Current runtime truth after tranche implementation

The most accurate current runtime interpretation is now:

- explicit Quran routing is materially healthy
- comparative 3-source tafsir is preserved across explicit explain paths
- explicit Hadith lookup/explain remains in scope
- public topical Hadith remains intentionally deferred
- bounded continuity remains live
- hosted query normalization is now implemented as a bounded pre-classifier layer
- observability and response-surface controls are now implemented
- bounded continuity substrate now has memory/sqlite/redis backend support with TTL and fallback behavior
- release posture / startup validation controls are now implemented
- a manual MVP test pack runner exists

## Remaining likely weakness areas before post-MVP expansion
Even after tranche implementation, the most likely remaining issues before broader post-MVP work are:
- integrated post-tranche regressions that only appear when the full bounded MVP pack is run together
- public answer-quality differences depending on renderer backend choice
- action-type cleanliness / scope honesty on large-surah asks
- concept-catalog breadth still needing more growth over time
- operational rough edges revealed by full production-style test runs

---

# 8) Immediate next step — do not skip this

The immediate next step is **not** a new capability tranche.

The immediate next step is:

## Full bounded MVP verification after latest tranche integration
The prepared test approach is:
1. startup / release posture checks
2. automated targeted tests
3. acceptance suites
4. manual bounded MVP pack via the PowerShell runner
5. review only failures/suspicious cases
6. classify outcomes into:
   - blocker
   - important
   - can wait

Until that happens, treat the current repo as:
- **productionization tranche sequence delivered**
- **full integrated verification pending**

---

# 9) What should happen after the full MVP pack

Only after the user runs the full post-tranche MVP pack and the outcomes are reviewed should the next chat decide whether:
- the current bounded MVP is ready to freeze as production-certified, or
- a short stabilization pass is still needed

## If the full MVP pack is clean enough
Then the current bounded MVP can be treated as effectively complete for production lock purposes.

## If failures remain
Then the next work should be a short stabilization pass, **not** immediate product-boundary expansion.

---

# 10) What should not be casually reopened

Do **not** casually reopen these in the next chat while full bounded MVP verification is still pending:
- public topical Hadith
- mixed-source public topical rollout
- broad generic Islamic chat
- persistent long-horizon memory
- LLM-led routing or source selection
- Continuity v2
- topical Tafsir expansion

The correct discipline is:
1. verify bounded MVP after latest tranche integration
2. stabilize only if needed
3. freeze the current bounded MVP if clean enough
4. only then discuss post-MVP expansion

---

# The Testing Status (Updated)

The manual MVP test pack was run and verified.
- Empty-evidence trust rules triggered correctly.
- Messy-input normalization successfully cleaned inputs and resolved to the correct domains.
- The Orchestrator successfully upgraded actions to `quran_with_tafsir` and retrieved 3-source comparative Tafsir accurately.
- Bounded follow-ups (e.g., "what about the next verse", "summarize this hadith") successfully hydrated session anchors and stayed within scope.
- Minor telemetry logging quirks (e.g., `action_type` logging as `fetch_text` instead of `explain`) were noted but did not affect the actual outward orchestration, retrieval, or user-facing composition. Let me know if we should fix that.

---

# 11) Post-MVP expansion lane — already agreed, do not forget

The post-MVP expansion lane to preserve for future handoffs is:

## Lane 1 — current MVP to production-grade
Already delivered in tranche plan form:
1. hosted query normalization
2. retrieval hygiene + catalog governance
3. observability / flags / contract lock
4. productionize current bounded continuity substrate
5. final production lock

## Lane 2 — post-MVP expansion
Preserved for later:
6. Continuity v2
7. topical Tafsir
8. topical Hadith

Important rule:
- hosted normalization is allowed only for **pre-classifier query cleanup**, not routing, source selection, policy, evidence gating, or continuation position.

---

# 13) Tranche — Continuity v2

Goal: move from bounded follow-up to a source-grounded reading companion.

Scope

First-class ContinuationIntent
Cursor / position model
Source-scoped continuation
continue, continue Ibn Kathir, continue from verse 20
skip intro, summarize what remains
Resume state in answer packet
Journey-level regression suite
---

# 13) Deferred / later ledger

These remain later:
- public topical Hadith
- Topical tafsir 
- mixed-source public topical answering
- persistent memory beyond bounded continuation substrate
- full response-contract cleanup
- object-storage migration for runtime artifacts
- additional source expansion
- expanded Quran navigation semantics including surah-absolute ordinal ayah targeting (deferred by explicit product decision unless later reopened)

# 14) Suggested instruction for the next coding / architecture chat

The next chat should start from this exact truth:

- the user has delivered and/or applied the tranche sequence for current MVP productionization
- the full integrated bounded MVP pack has **not yet been run after latest tranche integration**
- the next action is therefore **verification and stabilization**, not blind capability expansion
- any repo audit should explicitly separate:
  - what was historically green before tranche delivery
  - what has now been implemented in patch form
  - what still remains unverified until the user runs the full pack

## Preserve while moving forward
Any next work should preserve:
- explicit Quran behavior
- Arabic Quran quote behavior
- Quran explanation including tafsir by default in supported explicit lanes
- comparative 3-source tafsir
- explicit Hadith lookup/explain
- bounded anchored follow-up
- `/ask` as canonical public surface
- source-domain separation
- trust-first abstention behavior
- public topical Hadith disablement

---

# 15) Final practical note

The repo is no longer mainly blocked by “missing foundation.”

The current practical risk is now:

**mistaking delivered tranche work for completed certification, and widening scope before the full bounded MVP pack is actually run and reviewed.**

The next chat must avoid both mistakes:
- do not lose the tranche context
- do not overclaim certification before the full verification pass
