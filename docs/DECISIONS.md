# Decisions

Decisions the planning documents do not cover. Each entry says what was chosen and why. Newest last.

## Phase 0

### D-001. Defaults for settings the TRD lists without a value
`docs/TRD.md` section 7 names `CITEDESK_DB_PATH`, `OLLAMA_URL`, `SPAM_THRESHOLD` and `DRAFT_MAX_WORDS` but gives no defaults. Chosen:

| Setting | Default | Why |
|---|---|---|
| `CITEDESK_DB_PATH` | `data/citedesk.db` | `data/` is git-ignored, so the database file cannot be committed by accident |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama's own default address |
| `SPAM_THRESHOLD` | `0.8` | **Provisional.** Nothing exists to measure yet. Revisit in Phase 3 using the `tuned` split only |
| `DRAFT_MAX_WORDS` | `200` | **Provisional.** Revisit in Phase 5 after reading drafts |

### D-002. `/api/status` in Phase 0 reports only what exists
`docs/TRD.md` section 6 describes `/api/status` as model, knowledge base and database health plus the synthetic-data flag. In Phase 0 none of those components exist, so the endpoint returns `status`, `app`, `version`, `synthetic_data`, the configured model name, and a `components` block where each of `database`, `model` and `knowledge_base` is `"not_checked"`. It never reports `ok` for something it did not check. Real checks arrive with the database (Phase 2), the model (Phase 4) and the knowledge base (Phase 5). The response omits URLs and file paths.

### D-003. The server's bind address is a constant, not a setting
`docs/TRD.md` section 8 requires binding to `127.0.0.1` because v1 has no authentication. `python -m citedesk` passes `127.0.0.1` as a constant, and a test checks that no environment variable changes it. Only the port is configurable.

### D-004. Settings use `pydantic-settings`
It reads the environment and `.env`, validates types and ranges, and keeps the exact variable names from the TRD through field aliases. A test checks that `.env.example` lists exactly the settings in code and that its values equal the defaults, so the two cannot drift.

### D-005. Type checker: mypy (strict) on `citedesk/`
The plan allows mypy or pyright. mypy installs with pip, so the toolchain stays pip-only.

### D-006. Lint rules and formatter scope
Ruff lint rules: `E, F, I, B, UP, SIM, S` (the `S` security rules are on; tests may use `assert`). Line length 100. `docs/` and `web/` are excluded from ruff because recent ruff versions also format Markdown code blocks, and the planning documents should not be rewritten by a formatter.

### D-007. Lock files are `pip freeze` output
No lock tool is installed, so `requirements.lock` is the `pip freeze` of a clean runtime-only environment and `requirements-dev.lock` is the freeze of the development environment (runtime plus dev tools). They have no hashes. Regenerate both when `pyproject.toml` dependencies change. The dev lock was made on Windows and includes `colorama`, which is harmless on Linux.

### D-008. CI is tests and lint only
`.github/workflows/ci.yml` runs `ruff check`, `ruff format --check`, `mypy` and `pytest` on Ubuntu with Python 3.13, installing from `requirements-dev.lock`. It does not run the model, the knowledge base or any evaluation. The secret scan runs in pre-commit, as the plan says. First run on GitHub (2026-10-28, commit `5ad8063`) passed in 35 seconds.

### D-009. Secret scan: gitleaks through pre-commit
`.pre-commit-config.yaml` runs the `gitleaks` hook (pinned to `v8.30.1`) on staged files, using the default gitleaks ruleset in `.gitleaks.toml` with no allowlist. It was checked against a deliberately fake token and blocked it. Enable it on a fresh clone with `pre-commit install`.

### D-010. Line endings: LF
`.gitattributes` sets `* text=auto eol=lf` so files are the same on Windows and in CI.

### D-011. `web/` is not scaffolded in Phase 0
No Phase 0 task covers the web app, and the UI is built in Phase 6. `web/` exists as an empty directory so the layout matches `docs/TRD.md` section 3. The `run web` command is filled in when the app exists. The dev server will use a Vite proxy for `/api` to `127.0.0.1:8100` rather than enabling CORS (to be confirmed in Phase 6).

### D-012. `CLAUDE.md` is not tracked yet
`CLAUDE.md`, `CLAUDE.local.md` and `.claude/` are in `.gitignore`. They are assistant-instruction files, and whether to publish them is the owner's call. To track `CLAUDE.md`, remove it from `.gitignore`.

### D-013. Test client dependency
`fastapi.testclient` (Starlette) warns that `httpx` is deprecated for the test client and suggests a package called `httpx2`. It was not adopted: it was not possible to confirm who publishes it, and the warning is harmless today. Revisit if the warning becomes an error.

### D-014. Python version
`pyproject.toml` pins `requires-python = ">=3.13,<3.14"`, matching the stack in `CLAUDE.md`. The machine's default `python` is 3.14, so commands use `py -3.13` to create the virtual environment.

### D-015. Package metadata and install
`pip install -e . --no-deps` after `pip install -r requirements-dev.lock` makes the package importable while keeping the locked versions authoritative.

## Phase 1

### D-016. The demo business is an invented plumbing company, not a pet daycare
`docs/IMPLEMENTATION_PLAN.md` Phase 1 allows reusing the business from `rag-project/demo_docs` or generating a new one with `synthetic-business-universe`. A new one was generated. The original planning documents assumed a pet daycare, so these were changed to match (the schema still wins on names and values):

- `BACKEND_SCHEMA.md`: `service_type` is now `emergency_repair`, `drain_cleaning`, `water_heater`, `fixture_installation`, `inspection`, `other`, `unknown`. `pet_species` is replaced by `property_type` (`house`, `apartment`, `commercial`, `other`, `unknown`). The required-fields table, the `extractions.fields` example and the golden item example were rewritten. `pet_name`, `party_size`, `end_date` and `num_nights` no longer exist as extraction fields. No database column or `CHECK` constraint used these enums, so no migration changes.
- `PRD.md` (FR-7 and two phrases), `UI_UX_DESIGN_BRIEF.md` (mock-ups, the `HEALTH_SAFETY` wording, the sample draft) and `APP_FLOW.md` (one phrase) were updated.
- `address_area` is a new extraction field, required for `booking_request`, because a plumber needs to know whether the job is inside the service area.

Why plumbing: it has clearly bounded safety cases (gas smell, flooding, sewage, carbon monoxide), natural escalations for complaints, disputes and warranty exceptions, and priced jobs that exercise the figure check. The cost is that more inquiries cannot be answered from documents (price depends on diagnosis, availability is live), so fewer end in a fully drafted reply.

**Amendment (same day).** After comparing the fact sheet with the services menu of a real plumbing company's website (used only as a reference for which standard services exist; no names, wording or prices were copied), `service_type` gained `leak_repair` and `sewer_line_repair`, and the fact sheet gained a `services_offered` list, leak detection ($245, invented), and quote-only entries for sewer line repair and slab leak repair. General plumbing repair maps to `other`. Without these, ordinary requests such as "find a leak under my slab" would have escalated as `NOT_IN_KNOWLEDGE_BASE` and the labels would have been ambiguous. `tests/test_universe_facts.py` now checks that every `service_type` in the fact sheet exists in the schema enum, that no offered service clashes with the not-offered list, and that phone numbers and emails follow the synthetic-data rules.

### D-017. Only documents and inquiries are generated from the universe
The `synthetic-business-universe` skill also describes invoices, bookings and reviews. Citedesk needs none of them, so only `universe/facts.json`, the knowledge-base documents and the labelled inquiries are generated.

### D-019. Knowledge-base documents are generated and checked, never hand-edited
`tools/generate_kb_docs.py` renders eight documents (`about`, `emergencies`, `faq`, `hours`, `policies`, `pricing`, `service-area`, `services`) from `universe/facts.json`. They are deterministic, so there is no seed. `tools/check_consistency.py` fails if any dollar amount, percentage, time, date, phone number or email in a document is not in the fact sheet, and if any priced fact, service, closed date, staff name or not-offered item is missing from its document. Other numbers must at least appear somewhere in the fact sheet (a weak check; it catches invented figures such as "48 hours" but not a wrong-but-existing number). The generator refuses to write files if the check fails. Tests cover the generator and include deliberately wrong documents (wrong price, wrong time, wrong date, invented total, unknown phone and email, dropped items) to prove the checker catches them. The committed documents are also tested against a fresh render so they cannot drift.

Documents never refer to themselves ("see the Pricing document"), because that would teach the drafting model to write "according to the documents", which the `STRUCTURE` check bans. Headings follow the schema example (`pricing.md > Drain cleaning`).

Reading the output as a customer found fragments and a duplicated sentence caused by pasting fact-sheet text into sentences. Those were fixed in the generator, and the gas-smell instruction in the fact sheet was shortened so it no longer repeats "does not do gas work".

### D-020. No PDF document yet
The skill suggests one short PDF. `rag-project` does read PDFs (its passages carry a `page` number), so nothing blocks one, but no inquiry scenario needs it. Skipped; revisit only if page-number citations should be tested.

### D-021. What running rag-project showed (details in `docs/knowledge-base-contract.md`)
- **`/api/ask` has enough structure** for `retrievals.sources` (TRD open question 1: yes). There is no decline flag. `sources` is empty on a refusal, but not always: one "I don't know" answer still listed sources, and the same question gave different results on different runs. Phase 5 must decide the adapter's decline rule; a candidate (empty `sources`, or a refusal phrase in the first sentence, in code) is recorded in the contract.
- **Availability questions return partial answers, not declines.** They must be handled in code, not left to the knowledge base.
- **The not-offered list was restructured** into one short section per excluded service, following rag-project's own advice (one topic per section). On nine ad-hoc questions the exclusion passage reached the top 4 for 8 of 9 items, up from 0 of 9. One wrong answer remains (a restaurant is still said to be servable). It was **left unfixed on purpose**: editing the documents to fix a question I wrote myself would be tuning to my own test. Code routing on `property_type = commercial` and the Phase 5 checks are the intended defence. Expect this to appear in the evaluation and in the README's "where it goes wrong".
- **Question logging in rag-project is on by default.** Citedesk runs it with `RAG_LOG=0` so customer-derived questions are not written to its logs.
- Recorded responses are in `tests/fixtures/` for the Phase 5 contract test. They prove only that the format parses.

### D-022. Golden-set design (details in `eval/golden/README.md`)
- **Shape extended.** `BACKEND_SCHEMA.md` section 8 gave an item shape without a `category`, although the Phase 1 acceptance check asks for counts per category. Added: `category`, `evidence` (`{file, anchor}`, matched by text and verified against the documents), optional `sender_email`, optional `contains_sensitive_data`, a file header (name, version, reference date, author, document hash, counts). Section 8 was updated to match. The two documents were in tension here; the schema file wins on names, so it was changed rather than worked around.
- **Source of truth for enums is `docs/BACKEND_SCHEMA.md` for now.** `tools/golden.py` reads the enum rows from that file. Phase 2 creates `citedesk/models.py`; switch the import then. The required-fields table in `tools/golden.py` is likewise temporary and should be tested against `routing.py` in Phase 4.
- **Labels cannot disagree with the rules.** `expected_route` is derived from the labels by the TRD 4.3 rules and must match; `should_escalate` must equal "route is escalate"; `health_or_safety` requires `HEALTH_SAFETY`; `complaint` requires `COMPLAINT`; `NOT_IN_KNOWLEDGE_BASE` is only valid on the draft path.
- **Sender-email matching is unavailable in v1.** `BACKEND_SCHEMA.md` section 2 says a booking change or cancellation needs a booking reference "or sender email match", but the schema has no customer or booking table to match against. The golden set treats it as never matching, so a change or cancellation without a reference gets `request_details`. If a customer table is added later, revisit.
- **Emergencies are `health_or_safety`.** Gas smell, carbon monoxide, flooding, a burst pipe and sewage backup all carry `HEALTH_SAFETY` and `urgent`, and are escalated, not drafted. This is a labelling choice: a burst pipe is property damage rather than a health risk, but the owner should see it first and the queue shows urgent escalations at the top.
- **Hand-written, not generated.** The messiness (typos, run-ons, inconsistent dates) is written into the text rather than injected by a seeded script, because a script corrupts the facts the labels depend on. There is therefore no seed; the committed files are the data. The author is recorded in the file header.
- **Relative dates are null.** "Next Tuesday" and "this week" are ambiguous, so `start_date` is null and details are requested.
- The TRD's safety-net keyword examples were still pet-themed after the business change and have been replaced with plumbing terms.

### D-023. The tuned golden set: 135 items (details in `eval/golden/README.md`)
All 13 intents, all 18 categories and every escalation reason a labeller can know in advance are covered; `UNVERIFIED_FIGURE` and `MANUAL` appear at zero because they come from draft checks and reviewers, not from the message. `booking_flow` has 11 items instead of the planned 12 and `unanswerable` 7; the total is within the planned "about two thirds of 200".

Two findings from writing it that need an owner decision, neither changed unilaterally:
- **Gas water heaters.** The fact sheet prices water heater replacement but excludes "gas line or gas appliance work". A gas-fired heater is on that line. Recorded as an unanswerable item rather than resolved.
- **Commercial property has no routing rule.** The TRD routes only on reason codes, missing fields and spam; a complete booking request for a commercial building gets `draft_reply`, and only the knowledge base (which D-021 showed can say "yes") stands between the customer and a wrong answer. Phase 4 should decide whether to add a rule.

Small counts per label (for example 8 safety items, 2 legal threats) mean per-reason scores will be noisy; the evaluation report must say so.

### D-024. `tools/import_inquiries.py` and the intake payload it assumes (confirmed against the real API in Phase 3; see D-034)
`docs/TRD.md` section 6 names `POST /api/inquiries` but gives no request shape. The import tool posts `external_id`, `channel`, `sender_name`, `body`, and optionally `sender_email` and `subject`, as JSON. **This is an assumption**: Phase 3 builds the endpoint and should either accept this payload or change the tool. It was tested against a stand-in HTTP server on loopback and a fake transport, not against the real API, which does not exist yet. It treats HTTP 200 and 201 as created, 409 as already imported (the schema's unique index on `channel` plus `external_id` suggests the endpoint will say so), and anything else, or no connection, as a failure.

Rules built into the tool and covered by tests: labels, notes, categories and evidence are never sent; any address other than `127.0.0.1`, `localhost` or `[::1]` over `http` is refused; output contains ids and counts, never message text (rule 4 in `CLAUDE.md`); an inbox line with an unknown field is rejected, so a labelled file cannot be posted by mistake.

### D-018. Safety advice is a closed list in the fact sheet
`universe/facts.json` has a `safety_instructions` block (shut off the main water valve; gas smell; sewage backup; carbon monoxide alarm). It is the only advice a reply may contain. Anything else about fixing a problem goes to a person. How these replies are produced (a fixed template or a checked draft) is to be decided in Phase 4 or 5 when routing and drafting are built.

## Process

### D-025. One branch and one pull request per phase, from Phase 2
Phases 0 and 1 were committed directly to `main` and stay there. From Phase 2, each phase is built on its own branch (`phase-2-data-layer`, `phase-3-intake-screening`, and so on) with the usual small commits, one per task. At the phase's acceptance check the branch is pushed and a pull request is opened. Its description lists what was built, what passed, and anything unverified or assumed. CI must be green, and the owner merges. Why: CI then runs before code reaches `main`, and each phase becomes one page to review, with its acceptance check written down. Nothing is pushed and no pull request is opened until the owner asks. The branch only exists to hold the work; `main` is unchanged until the merge.

## Phase 2

### D-026. Database conventions and what the migration runner cannot do
`citedesk.db.connect` opens SQLite in autocommit mode (`isolation_level=None`) with foreign keys on, rows as mappings, and WAL for file databases. Grouped statements use `transaction()`, which commits on success, rolls back on any exception, and joins an open transaction. Each migration runs in its own transaction together with its `schema_migrations` row, so a failure leaves nothing half applied. `0001_init.sql` is extracted from the SQL block in `BACKEND_SCHEMA.md` and a test compares them character for character.

Limits worth knowing: `schema_migrations` has no checksum column (the schema document defines it exactly), so editing an already-applied migration is **not detected**; "never edit an applied migration" stays a convention. The runner refuses a gap in numbering, a duplicate number, a badly named file, and a database newer than the code. Connections use SQLite's default `check_same_thread`, so Phase 3 must open one connection per request or worker rather than share one across FastAPI threads.

### D-027. Models and the enum checks
`citedesk/models.py` holds every enum and one row model per table. Four enums are not in the schema's section 1 table but are needed: `ScreeningResult`, `EscalationSource` and `ExportMethod` (values from `CHECK` constraints) and `AuditEventType` (from a comment on `audit_events.event_type`, which has no `CHECK`). Tests read the `CHECK` constraints back out of a migrated database and compare them with the enums, compare the enums with the schema document's table, require a row model for every table whose fields equal its columns, and fail if an enum exists that none of those sources accounts for. `Channel.import_` has a trailing underscore because `import` is a Python keyword; its value is still `"import"`. `tools/golden.py` now takes its enums from here.

### D-028. Repository rules that go beyond the schema
- `update_inquiry` cannot change `status` (or the message); only `state.transition` does, and a test fails if any other module writes `inquiries.status`.
- A new draft starts as **`blocked`**, not the database default `ready`: a draft is not ready until its checks have run. `set_draft_status` refuses `ready` or `approved` while any blocking check has failed, raising `DraftBlocked`. This enforces "no draft with a failed blocking check is ever marked ready" at the data layer, as a floor under whatever the Phase 5 pipeline does.
- Re-running a stage is safe: screenings and draft checks are upserts, and an open escalation with the same reason is reused instead of duplicated.
- An extraction must belong to a classification of the same inquiry; an escalation `detail` is capped at 200 characters.

### D-029. State machine details, and two gaps in the schema's table
`citedesk/state.py` holds the 20 allowed moves, written out in code and compared in a test with the table in `BACKEND_SCHEMA.md` section 5; every one of the 169 status pairs is tested. The "failed returns to the prior stage's input status" row needs a mapping, chosen here: failed at `screen` returns to `received`, `understand` to `screened`, `retrieve` or `draft` to `routed`. Each status may fail only at its own stages. A failure message is capped at 300 characters and may not contain a 20-character run of the customer's own words. `transition()` updates the status, sets or clears the failure fields, and writes the `status_changed` event in one transaction.

**Gap for Phases 4 and 5:** the table has no way to fail from `classified` (so a crash in the route stage) or from `drafted` (a crash in the check stage). If the pipeline needs either, `BACKEND_SCHEMA.md` section 5 and `state.py` must change together; do not catch the error and leave the inquiry stuck.

### D-030. Audit events: what counts as message text, and what this cannot catch
`events.record_event` is the only writer of `audit_events` (a test enforces it). A payload must be flat; keys are snake_case names; values are numbers, booleans, null, or short code-like tokens (no spaces, at most 64 characters, no `@` or `/`, no phone-like digits) or flat lists of those. A token that appears as a whole word in that inquiry's own body, subject, sender name or email is refused unless it is a known code from the enums. A rejection never repeats the rejected value, because the exception may be logged. This blocks sentences and single words lifted from the message. It cannot catch a paraphrase, a word from a different inquiry, or a harmless-looking token that happens to be sensitive. The structured log helper in the TRD's `events.py` is not written yet; it should reuse `validate_payload` when the pipeline needs it (Phase 3), and Phase 8 verifies logs.

## Phase 3

### D-031. Screening runs at intake, before the first write
The documents say both "mask sensitive values before the body is stored" (TRD 4.1) and "write the inquiry with status `received` before any processing" (APP_FLOW 4.1). Read literally they conflict: masking is processing. Resolved as follows. `intake.submit` runs the screening detectors (pure code, milliseconds, no model) and writes the inquiry and its `screenings` row in **one transaction**, with the body already masked. The pipeline's screen stage then applies the stored result. So an unmasked number is never on disk, not even for a moment, and everything slow (the model, the knowledge base) still happens after the write. If screening itself crashes, intake stores **nothing** and returns a 500: refusing is safer than keeping text that was never checked, at the price that the caller must retry. Tests look at every cell of every table for the original card digits.

### D-032. The detectors, what they flag, and what they deliberately do not
All are pure functions in `citedesk/screening.py`; results hold pattern names, never matched text.
- **Card numbers:** 13 to 19 digits, either contiguous or grouped like a card (4-4-4-4, 4-6-5), passing the Luhn check, and not a single repeated digit. Masked as `**** **** **** 1111` (last four kept). A 16-digit invoice number that fails Luhn is left alone. About one in ten random 16-digit numbers passes Luhn, so a coincidental order number will occasionally be masked; that is the safe direction.
- **Government IDs:** **TRD 4.1 says "the authoritative lists of values are in `BACKEND_SCHEMA.md`", but that file has no such list.** Chosen: US Social Security numbers only, either formatted (`123-45-6789` or with spaces) with the structural rules (area not 000, 666 or 9xx; group not 00; serial not 0000), or nine bare digits within a few characters of "SSN" or "social security". Passports, driving licences and bank numbers are not covered; say so in the README.
- **Injection:** a message is flagged if any *strong* pattern matches (ignore previous instructions, reveal the system prompt, persona swap, "do not tell staff", decode-and-follow), or if two different *weak* patterns appear together (claims to be the owner, "I authorise you to", a JSON reply template, "format your reply as JSON", "reply that ... is confirmed"). Base64 blobs are decoded and the strong patterns run on the result. **Not flagged on purpose**, because real customers write them: "ignore my earlier message", "I am the owner of the house", "I authorise you to go ahead", "you are now my favourite plumber", "give me instructions for the main valve". A customer who writes "ignore the previous instructions" about their own request will be escalated; a person reads it.
- **Spam:** a weighted score (spam phrases, links, link-only text, runs of "!", capital letters, money hype, a phishing combination, and no plumbing vocabulary). Capital letters alone add 0.1, so an urgent message in capitals can never be archived. The threshold stays at the provisional 0.8 (D-001). Injection beats spam; an emergency term vetoes archiving; a sender with an earlier clean inquiry (the only definition of "known customer" v1 can support, since there is no customer table) is not archived.
- **Result on the tuned golden set:** every spam item scores at least 0.90 and no real inquiry scores above 0.20; exactly the six labelled injection items are flagged, none of the near-misses; the one card number is masked and the Luhn-failing invoice number is not. **These detectors were written with that set in view**, so this shows the machinery works, not how it generalises. The held-out set is the honest test.
- **For Phase 4:** the emergency keyword net over-fires on two items that mention past events ("flooded my kitchen" in a legal threat, "a pipe burst last month") and misses one safety item that never uses a keyword (sewage on the laundry floor). Both are measurable on the golden set.

### D-033. Intake rules the documents left open
Limits: body 1 to 10,000 characters (`MAX_BODY_CHARS`), subject 300, sender name and ids 200, email 254. Control characters are removed, line breaks kept; emails are lower-cased; `received_at` is normalised to UTC and refused if more than five minutes in the future. A repeated `(channel, external_id)` is refused with 409 and the existing id. **Duplicate window: 24 hours** (`DUPLICATE_WINDOW_HOURS`, 0 turns it off): the same sender (email, or name if there is no email) sending the same subject and body after masking and normalising case and spacing. A duplicate is stored as its own row with `duplicate_of` set, then the screen stage archives it. **This differs from APP_FLOW 4.1**, which says duplicates show "in the queue": the review queue lists only `needs_review`, `escalated` and `failed`, so a duplicate appears under the archived filter and in the original's detail (`duplicates`), not in the queue itself.

### D-034. API choices
One error shape `{error: {code, message, request_id}}` on every failure, with an `X-Request-ID` header on every response; messages never repeat what the caller sent (field names only). A database connection is opened inside each request, because FastAPI may run a dependency and its endpoint on different threads and SQLite connections are thread-bound. `POST /api/inquiries/import` takes the file as the **raw request body** (`application/x-ndjson` or `text/csv`, 5 MB, 5,000 records) rather than a multipart upload, which would need an extra dependency; a bad line never stops the others and the summary holds line numbers and codes only. Lists use keyset paging in review-queue order, so new arrivals cannot make a page skip or repeat a row. `/api/status` now checks the database and reports queue depth and whether the worker runs; model and knowledge base stay `not_checked`. Webhooks use the same endpoint with `channel: webhook`. **Settles D-024:** the real import tool, run against the real server, stored all 135 messages and treats 409 as "already imported". Not built yet, by design: reprocess, drafts, review decisions, export and insights (later phases).

### D-035. The worker, and what is not logged
The screen stage does all its work (status changes, escalations, route, audit events) in one transaction, so a crash leaves the inquiry at `received`, where it can fail cleanly with `failure_stage = screen` (the state table allows nothing else; see D-029). The stage is retried once, then the inquiry is marked `failed` with a message naming only the exception type. The worker thread polls every two seconds and wakes on each new inquiry; one worker per process, one inquiry at a time, and a second process would be safe because the status is checked inside the transaction. Suspected-injection items get route `escalate` but no urgency unless an emergency term is present (then `HEALTH_SAFETY` and `urgent`), because no model reads them. No structured log helper exists yet: the code logs only ids and exception type names, and Phase 8 verifies that no message text reaches a log.

## Phase 4

### D-036. A failed route stage: `classified` to `failed` (settles the first gap in D-029)
The state table had no way to fail from `classified`, so a crash in the route stage would have left an inquiry stuck there with the worker retrying it forever. Added `classified` → `failed` ("route stage crashed after retry") to `BACKEND_SCHEMA.md` section 5, `state.py` (`ALLOWED`, and `RETRY_TARGET[route] = classified`) and the state tests, together, as D-029 asked. A retry returns to `classified`. The second gap in D-029 (`drafted` has no failure move, for a crash in the check stage) is **left open on purpose**: nothing in Phase 4 needs it, and a test now pins that `drafted` still refuses to fail, so Phase 5 has to decide it knowingly.

### D-037. The emergency net, extended and measured (`citedesk/safety.py`)
D-032 named three disagreements between the net and the tuned golden set: it fired on two items that mention something past, and missed `safety-sewage-on-laundry-floor`, which never uses a keyword. Two changes, both in code and covered by tests:

- **Sewage can be described instead of named.** Foul water on a floor ("dirty smelly water ... on the laundry room floor"), toilet paper next to a floor, tub, shower, sink or drain, water "coming up out of" a floor drain, toilet, tub or shower, and a toilet that overflows. Ordinary drain talk does not fire (a slow or gurgling sink, a toilet-paper holder, brown tap water, bubbles in a toilet when the washer drains); the tests list these near-misses.
- **A historical mention is discounted.** A match is dropped if its own clause says it was long ago ("last month", "two years ago", "back in 2019", "the last time") and does not also say it is happening again ("again", "still", "today", "this morning"). A clause ends at punctuation or at "and", "but", "so", "because", "now", "please", "then", so "flooded last year please help water everywhere" still fires on the second half. "Last week" and "last night" are **not** historical: that water may still be there.

**Measured on the tuned split (135 items, label `HEALTH_SAFETY` against "the net fired"):** before, 7 of 8 safety items caught, 2 over-fires; after, 8 of 8 caught, 1 over-fire. The remaining over-fire is `legal-sue-over-water-damage` ("your plumber's repair failed on Sunday night and flooded my kitchen"): nothing in the clause says it is over, so it fires. It escalates for `LEGAL_THREAT` anyway, so the route is unchanged; the extra `HEALTH_SAFETY` reason and `high` urgency are noise the reviewer will see. A test pins exactly this one item.

**What this cannot tell you.** The net was extended with these items in view, so 8 of 8 shows the rules agree with the labels, not how well they generalise; eight safety items cannot bound a miss rate much better than "up to about one in three". Hypotheticals and prevention ("to stop pipes bursting this winter", "in case of a flood") are not discounted; they fire and a person looks. A historical marker in a different sentence from the term ("The pipe burst. That was last month.") does not discount it.

**What the net does with a hit (TRD 4.2, as written):** urgency is raised to **at least `high`** and `HEALTH_SAFETY` is added with source `safety_net` when the model did not already flag it. This differs from D-035, where a suspected-injection item with an emergency term gets `urgent`: there no model reads the message, so the net is all there is. Where a model has read it, the model's own `urgent` is kept and the net is only a floor.
