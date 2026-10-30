# Implementation Plan: Citedesk

Version 0.1. Read `PRD.md`, `TRD.md`, `APP_FLOW.md`, `UI_UX_DESIGN_BRIEF.md` and `BACKEND_SCHEMA.md` first. Where documents disagree, `BACKEND_SCHEMA.md` wins on names and values, `TRD.md` wins on behavior.

## How to work

- Build in the phase order below. Each phase ends with something runnable and a short acceptance check. Do not start a phase until the previous one passes.
- Write tests first for every rule that is plain code (routing, checks, state machine, screening). Model behavior is measured by the evaluation, not asserted in unit tests.
- Commit at the end of each task. Keep commits small. Never commit secrets, real data or the database file.
- Rely on fakes (`FakeLLM`, `FakeKB`) in tests so the suite needs no model, network or GPU.
- When a decision is not covered by the documents, pick the simplest option, record it in `docs/DECISIONS.md` with the reason, and move on.
- Report evaluation numbers exactly as they come out. Do not tune on the held-out set.

Skills that help, if installed: `synthetic-business-universe` (phase 1), `ai-ui-patterns` and `frontend-design` (phase 6), `qa-eval-harness` (phases 1 and 7), `pre-publish-checklist` (phase 9), `project-case-study-readme` (phase 9).

## Phase 0: Repository and tooling

Tasks
1. Create the repo `citedesk` with the layout in `TRD.md` section 3. The planning documents live in `docs/`, and `CLAUDE.md` sits at the repo root.
2. Python 3.13 virtual environment; `pyproject.toml`; pinned `requirements.lock` and `requirements-dev.lock`.
3. FastAPI app skeleton with `GET /api/status`.
4. Settings from environment with `.env.example`; `.gitignore` covering `.env`, database files, virtual environment, `node_modules`, eval run outputs except published ones.
5. pytest, ruff (lint and format), mypy or pyright on `citedesk/`.
6. GitHub Actions workflow running tests and lint only.
7. `.gitleaks.toml` and a pre-commit secret scan.
8. `README.md` stub stating it is a work in progress and that all data is synthetic.

Acceptance: `pytest` passes with one smoke test; CI is green; `/api/status` returns JSON on port 8100.

## Phase 1: Synthetic data and golden set

Tasks
1. Decide the business: use the fictional business from `rag-project/demo_docs`, or generate a new one with `synthetic-business-universe`. Write `universe/facts.json` (prices, hours, policies) and keep the knowledge-base documents consistent with it.
2. Make sure `rag-project` indexes those documents and answers a few test questions. Record the exact `/api/ask` request and response shape in `docs/knowledge-base-contract.md`.
3. Generate about 200 synthetic inquiries covering every intent, multi-intent, vague, urgent, angry, spam, out-of-scope, follow-up and injection attempts. Messy writing: typos, missing details, inconsistent dates.
4. Label each (see the golden item shape in `BACKEND_SCHEMA.md`) and assign splits: write the first two thirds as `tuned`; write the final third later as `heldout`, after the prototype exists (see Phase 7).
5. A schema file for the golden set and a validator command.
6. `tools/import_inquiries.py` to load a JSONL inbox through the API.

Acceptance: validator passes; counts per intent and category printed; a README for the data states it is invented and lists known gaps (data is cleaner than real writing).

## Phase 2: Data layer

Tasks
1. Migration runner and `0001_init.sql` exactly as in `BACKEND_SCHEMA.md`.
2. Pydantic models and enums in `models.py`; a test that the enums in code match the `CHECK` constraints in the database.
3. Repository functions for each table (plain SQL, no ORM) with tests on an in-memory database.
4. State machine function with a test for every allowed and every disallowed transition.
5. Audit event helper that refuses payloads containing message text (test it).

Acceptance: all migrations apply to an empty database; transition tests pass; no model needed.

## Phase 3: Intake and screening

Tasks
1. `POST /api/inquiries`, `GET /api/inquiries`, `GET /api/inquiries/{id}`, import endpoint.
2. Validation, duplicate detection, write-before-process.
3. Screening: spam score, injection patterns, sensitive-data masking (Luhn check, ID patterns).
4. Unit tests with a list of positive and negative examples for each detector, including tricky near-misses (an order number that looks like a card number; a customer saying "ignore my earlier message").
5. Pipeline worker skeleton processing one inquiry at a time with `received → screened` and the archive and injection exits.

Acceptance: importing the synthetic inbox stores every item; spam and injection items end in `archived` or `escalated`; masked bodies never contain the original number.

## Phase 4: Understanding and routing

Tasks
1. `LLMProvider` interface, `OllamaProvider`, and `FakeLLM`.
2. Classification and extraction prompt (`understand-v1`) returning schema-validated JSON; retry once on invalid output; timeout, token cap, one retry without thinking.
3. Safety net for emergency terms in code.
4. Required-fields table and `missing_fields` computation.
5. Routing rules and reason codes as pure functions with exhaustive tests.
6. Pipeline stages `understand` and `route`, with audit events.
7. A small scoring script that runs the `tuned` split through stages 1 to 3 and prints intent accuracy, field accuracy and escalation precision and recall.

Acceptance: pipeline reaches `routed`, `escalated` or `archived` for the whole inbox without crashes; the scoring script runs; numbers recorded in `docs/DECISIONS.md` as the first baseline (whatever they are).

## Phase 5: Retrieval, drafting and checks

Tasks
1. `KnowledgeBase` interface, `RagProjectKB`, `FakeKB`, and a contract test using a recorded response.
2. Question builder for single and multi-intent inquiries.
3. Draft prompt (`draft-v1`) returning `{subject, body, claims}`; `request_details` template; holding-reply option when the knowledge base declines.
4. Checks in `checks.py`: `FIGURES_GROUNDED`, `NO_COMMITMENT`, `CLAIMS_HAVE_SOURCES`, `STRUCTURE`, `NO_INJECTION_ECHO`. Each has unit tests with passing, failing and edge cases (derived sums, dates written two ways, quotes of source text).
5. Pipeline stages `retrieve`, `draft`, `check`, including the blocked-draft escalation path.
6. Manual read of 30 drafts; write what looks wrong in `docs/DECISIONS.md`.

Acceptance: every non-escalated inquiry in the tuned set ends in `needs_review` with sources attached, or in `escalated` with a named reason; no draft with a failed blocking check is ever marked ready (test with deliberately bad fake drafts).

## Phase 6: API completion and review UI

Tasks
1. Review endpoints: approve, reject, redraft, manual escalate, resolve, export; `GET /api/insights`.
2. Generate TypeScript types from the OpenAPI schema; add a check in CI that the generated file is current.
3. Run the `frontend-design` skill: produce the design plan against `UI_UX_DESIGN_BRIEF.md` and review it before coding.
4. Build the screens in this order: Queue, Inquiry detail (ready, escalated, blocked, failed, refusal variants), Insights, Settings. Use the patterns in `ai-ui-patterns`.
5. Keyboard flow, live regions, 360px layout, reduced motion.
6. Component tests for empty, loading, error, refusal and success states on each screen.
7. Record a walkthrough GIF and screenshots at desktop and phone widths, including the refusal and blocked states.

Acceptance: a reviewer can go from queue to approved reply using only the keyboard; all five states exist on each screen; UI tests pass.

## Phase 7: Evaluation

Tasks
1. Write the held-out third of the golden set now, in new wording, after the prototype exists. Run it once before any tuning on it and report that score.
2. Runner and scorer as separate commands; saved runs record commit, settings, model, prompt versions and the golden hash.
3. Metrics: intent accuracy and macro-F1, urgency accuracy, field accuracy, escalation precision and recall by reason, route accuracy, check pass rates, ungrounded figures, injection outcomes, latency.
4. Repeat runs (3 to 5) to measure run-to-run spread; compare thinking on and off using the spread test described in `qa-eval-harness`.
5. Report with a "what this cannot tell you" section; list the worst misses case by case.
6. Optional: add an adapter so `citecheck` can score the drafts' groundedness.

Acceptance: a Markdown report and a JSON copy committed under `eval/reports/`; held-out numbers separate from tuned numbers; the zero-miss target for `HEALTH_SAFETY` stated as met or missed with the count.

## Phase 8: Hardening

Tasks
1. Rate limit and size limit on intake; request ids on every response.
2. Confirm logs and audit events contain no message or draft text (test).
3. Test prompt-injection items from the golden set end to end; document what still gets through.
4. Check failure paths: model offline, knowledge base offline, invalid JSON twice, database locked.
5. Dependency audit (`pip-audit`, `npm audit`) and fix high or critical findings.

Acceptance: failure-path tests pass; the README's known-weaknesses section matches what the tests show.

## Phase 9: Documentation and publish

Tasks
1. Use `project-case-study-readme` to write the README: what it does, how it works, design decisions with numbers, how well it works, what the numbers do not say, where it goes wrong, how to run it, what to improve.
2. Run `pre-publish-checklist`: secrets in history, personal data, licensing, synthetic labelling, claims versus evidence, fresh-clone run, CI.
3. Write the Docker Compose setup if wanted; test from a fresh clone.
4. Add a short "what this could save" section with every assumption labelled.

Acceptance: a stranger can clone and run the demo with the documented commands; the checklist report has no FAIL items or each is explained.

## Stretch (after v1)

- Hosted model provider (Claude API behind `LLMProvider`) with cost per inquiry reported and a documented warning that message text goes to the provider.
- Gmail draft creation behind `MailExporter` (create drafts only, never send).
- n8n workflow that posts web-form submissions to `/api/inquiries`.
- Reranking or hybrid search added to the knowledge base, measured with the same evaluation.
- A review screen that points at what the checks cannot see (the price's source line and service, the greeting name beside the sender, sentences no source backs), then a rerun of the reviewer trial with new plants and ideally a second reviewer (D-066, D-067). Not built: it needs the rerun to claim anything.
- A real pilot with a willing business: consent, anonymization, and a separate evaluation.

## Risks to watch while building

| Risk | Early sign | Response |
|---|---|---|
| Classification accuracy is low on multi-intent messages | Many items with the wrong primary intent | Split into two calls (intent, then fields) and re-measure |
| Model JSON invalid often | Retries above about 5 percent | Simplify the schema; shorten the prompt; lower token cap |
| Figure check blocks too many good drafts | Many `UNVERIFIED_FIGURE` escalations on correct drafts | Inspect misses; improve normalization (currency, dates); do not loosen the check without evidence |
| Knowledge base returns weak sources for multi-topic messages | Drafts skip half the question | Ask one question per intent (already planned); check `rag-project`'s split search |
| Time spent on the UI crowds out evaluation | Phase 6 over budget | Ship Queue and Detail first; Insights and Settings can be minimal |

## Definition of done for v1

- All MVP functional requirements in the PRD are met or explicitly marked deferred with a reason.
- Unit and component tests pass in CI without a model.
- Held-out evaluation run once, reported with limits.
- No automatic sending path exists anywhere in the code.
- README, case study and checklist report are complete, and all data is labelled as invented.

## First prompt to give Claude Code

> Read CLAUDE.md, then read PRD.md, TRD.md, APP_FLOW.md, UI_UX_DESIGN_BRIEF.md, BACKEND_SCHEMA.md and IMPLEMENTATION_PLAN.md in docs/. Work through Phase 0 and then stop and show me what exists and how to run it. Use the names and values in BACKEND_SCHEMA.md exactly. Write tests first for anything that is plain code. Record decisions that the documents do not cover in docs/DECISIONS.md.
