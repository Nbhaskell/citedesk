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

### D-018. Safety advice is a closed list in the fact sheet
`universe/facts.json` has a `safety_instructions` block (shut off the main water valve; gas smell; sewage backup; carbon monoxide alarm). It is the only advice a reply may contain. Anything else about fixing a problem goes to a person. How these replies are produced (a fixed template or a checked draft) is to be decided in Phase 4 or 5 when routing and drafting are built.
