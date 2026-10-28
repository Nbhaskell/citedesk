# Product Requirements Document: Citedesk

Name: Citedesk (repo `citedesk`)
Version: 0.1 (draft for build)
Owner: project author
Status: ready for implementation

## 1. Summary

Citedesk reads incoming customer messages for a small service business (web forms and email), works out what each customer wants, pulls the missing details, decides whether a person must handle it, and writes a draft reply grounded in the business's own documents. A staff member reviews every draft before anything goes out. Nothing is sent automatically.

It is the second building block of a small-business AI suite. It reuses the author's `rag-project` as its knowledge base and is evaluated with the same discipline as `citecheck`: a golden set, a held-out split, and reported limits.

## 2. Problem

Small businesses answer the same questions all day (prices, hours, availability, policies) across email and web forms. Replies are slow outside business hours, urgent messages get buried among routine ones, and the details needed to book (dates, the type of job or product, the address or area) are often missing and have to be asked for in a second round of messages.

An unattended chatbot that answers customers directly is risky for a business with no engineering team: a wrong price, a promised refund, or a missed emergency costs real money and trust. The product therefore puts a human in charge and makes the review fast.

## 3. Users

| Persona | Needs |
|---|---|
| Owner-operator (primary buyer) | Fewer after-hours messages to deal with, nothing urgent missed, confidence that wrong answers do not go out |
| Front-desk or admin staff (primary daily user) | A sorted queue, a ready draft they can check in under a minute, clear reasons when something needs a person |
| Customer (indirect) | A fast, correct, polite reply; not being asked twice for the same details |

## 4. Context and assumptions

- There is no real client yet. v1 runs entirely on a synthetic business and synthetic inquiries, labelled as such everywhere. Results on synthetic data show the machinery works; they do not show behavior on a real business's messy inbox.
- The knowledge base is `rag-project` running locally. The fictional business in its `demo_docs/` is the default business.
- Local-first: a local model (Ollama, `qwen3:8b`) and no outside service is required. A hosted model is a later, optional provider.
- One business, one reviewer at a time. No accounts or multi-tenancy in v1.

## 5. Goals

1. Classify each inquiry by intent (one or more), urgency and sentiment.
2. Extract booking-relevant fields and identify which are missing.
3. Decide a route: draft a reply, ask for missing details, escalate to a person, or archive as spam.
4. Draft a reply grounded in the business's documents, with the sources visible to the reviewer.
5. Block unsafe drafts with checks written in code (ungrounded figures, promised refunds, confirmed bookings).
6. Give the reviewer a fast approve, edit, or reject flow with an audit trail.
7. Measure all of the above on a held-out set and publish the numbers, including the weak ones.

## 6. Non-goals (v1)

- Sending email or messages automatically. The product only produces drafts and exports them.
- Real customer data, multiple businesses, accounts and login, billing.
- Taking actions in outside systems (creating bookings, charging cards). That is the separate action-taking chatbot project.
- Phone and SMS channels, attachments, images.
- Learning from edits automatically. Edits are recorded for later analysis only.

## 7. Success metrics

Targets are starting hypotheses. Replace them with the measured baseline after the first evaluation, and report what was actually measured.

| Metric | Initial target | How measured |
|---|---|---|
| Primary-intent accuracy | at least 0.85 on held-out | Golden set, exact match on `primary_intent` |
| Escalation recall for `HEALTH_SAFETY` | no misses on the held-out set (report n) | Golden set items labelled `should_escalate` |
| False escalation rate | at most 0.20 | Escalated items that should not have been |
| Field extraction accuracy | at least 0.90 on required fields | Per-field match against labels |
| Ungrounded figures in drafts that pass checks | 0 | Code check over all drafts, plus manual read of 30 |
| Prompt-injection resistance | measured and reported, not assumed | Adversarial items in the golden set |
| Reviewer time per inquiry | measured in a small timed trial | Stopwatch on 20 items; assumptions labelled |
| Median time from receipt to draft ready | under 30 seconds on the dev machine | Pipeline timing events |

## 8. User stories

1. As staff, I open a queue sorted by urgency, so the important messages come first.
2. As staff, I see what the system understood (intents, dates, property, service) next to the original message, so I can spot misreadings.
3. As staff, I see a draft with its sources and which checks passed, so I can verify it quickly.
4. As staff, I edit the draft and approve it, or reject it with a reason, so the record shows what happened.
5. As an owner, I see urgent and sensitive messages flagged with the reason, so nothing serious waits in the queue.
6. As an owner, I see counts of handled, approved unchanged, edited, rejected and escalated, so I can judge whether it helps.
7. As the author, I run an evaluation and get a report of scores with limits, so I can publish honest results.

## 9. Functional requirements

Priority: M = must for v1, S = should, C = could.

**Intake**
- FR-1 (M) Accept an inquiry by `POST /api/inquiries` (JSON: channel, sender name and email, subject, body, received time, optional thread id).
- FR-2 (M) Import a JSONL or CSV file of inquiries for the synthetic inbox.
- FR-3 (S) Accept a form-builder or n8n webhook with the same JSON.
- FR-4 (C) Import `.eml` files.

**Screening**
- FR-5 (M) Flag likely prompt-injection text, obvious spam, and sensitive data (card or government-ID numbers) before any model reads the message. Spam is archived, suspected injection is escalated before any model reads it, and sensitive data is masked in place and the inquiry continues with a warning to the reviewer.

**Understanding**
- FR-6 (M) Classify into one or more intents from the fixed list in the Backend Schema, with a primary intent, urgency and sentiment, via structured model output validated against a schema.
- FR-7 (M) Extract fields (service type, preferred date, property type, address area, preferred contact) and compute `missing_fields` in code from required fields per intent.
- FR-8 (M) Record the model, prompt version and raw response for every classification.

**Routing**
- FR-9 (M) Choose a route in code from classification, extraction and screening: `draft_reply`, `request_details`, `escalate`, `archive`.
- FR-10 (M) Escalate, with a reason code, for health or safety, complaints, refund or dispute, legal threats, policy exceptions, low confidence, injection suspicion, and when the knowledge base cannot answer.

**Drafting**
- FR-11 (M) For `draft_reply`, query the knowledge base with a standalone question built from the inquiry, keep the returned sources, and draft a reply from those sources only.
- FR-12 (M) For `request_details`, draft a short reply asking only for the missing fields.
- FR-13 (M) Run draft checks in code (see TRD): figures grounded, no commitments, structure and length, no injection echo.
- FR-14 (M) A draft that fails a blocking check is not shown as ready; it is routed to a person with the failed check named.
- FR-15 (S) Offer one redraft with the reviewer's reason as guidance.

**Review**
- FR-16 (M) Queue with filters (needs review, escalated, archived, all) and sort by urgency then age.
- FR-17 (M) Detail view: original message, "Understood as" panel, draft editor, sources panel, checks list, history.
- FR-18 (M) Approve, edit-then-approve, reject (with reason), manually escalate. Every action is stored.
- FR-19 (M) Export an approved reply as copyable text. Drafts may be created in a mail account later (FR-26), never sent.

**Insights**
- FR-20 (S) Counts by route and decision, share approved unchanged, share edited, median time to review.

**Evaluation**
- FR-21 (M) A golden set of at least 150 labelled synthetic inquiries, with tuned and held-out splits.
- FR-22 (M) `run` and `score` commands separated, saved runs, and a report that lists limits.

**Operations**
- FR-23 (M) Everything runs locally with documented commands; API binds to 127.0.0.1.
- FR-24 (M) Structured event log with no message or draft text.
- FR-25 (M) Synthetic data is labelled in the UI and the README.
- FR-26 (C) Create drafts in Gmail through an authorised connection. Never send.

## 10. Non-functional requirements

- **Safety:** nothing leaves the system without a person approving it; no automatic sending in any mode.
- **Privacy:** local-first; the database file is git-ignored; logs exclude message and draft text; a hosted-model mode documents that message text goes to that provider.
- **Reliability:** each pipeline stage is retried once and then marked `failed` with a visible reason; a failed model call never produces a silent empty draft.
- **Latency:** local 8B model on a consumer GPU; classification plus drafting under 30 seconds median. Model calls have a timeout and a token cap.
- **Accessibility:** keyboard path for the full review flow; screen-reader friendly status changes.
- **Maintainability:** model, knowledge base and mail export each sit behind an interface so they can be swapped.
- **Testability:** all code-checked rules have unit tests that need no model; model-dependent behavior is measured by the evaluation, not unit tests.

## 11. Scope and phasing

- **MVP (v1):** FR-1, 2, 5 through 14, 16 through 19, 21 through 25.
- **v1.1:** FR-3, 15, 20.
- **Later:** FR-4, 26, hosted-model provider, multi-business, real pilot with consent.

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Model misclassifies and routes an emergency to the normal queue | Keyword safety net in code in addition to the model; zero-miss target on the held-out set; urgent items sorted first |
| Draft states a wrong price | Figure check against sources and fact sheet blocks the draft |
| Draft promises a refund or confirms a booking | Commitment check in code with configurable patterns |
| Prompt injection in a message or document | Screening, structured outputs, drafts never executed as instructions, adversarial items in the golden set; known weaknesses documented |
| Synthetic data too clean, scores flattering | Messy generation, sealed held-out set, explicit limits section |
| 8B model stalls or loops | Token cap, timeout, one retry without thinking (learned in `rag-project`) |
| Port conflicts with `rag-project` and `citewise-markets` (both use 8000) | Citedesk API uses 8100 |

## 13. Dependencies

- `rag-project` running locally (`/api/ask`). Confirm the exact request and response shapes against its `guides/api.md` at build time.
- Ollama with `qwen3:8b`.
- Synthetic business data (from the `synthetic-business-universe` skill or the demo documents).

## 14. Open questions

1. Should the knowledge base be called over HTTP or imported as a library? Default: HTTP behind an adapter.
2. Should `request_details` and `draft_reply` be combined when both apply? Default: one draft that answers what it can and asks for what is missing.
3. Is a Gmail draft-creation connector in scope for the portfolio version? Default: later.
4. Which hosted model, if any, for the demo? Default: decide after the local baseline.
