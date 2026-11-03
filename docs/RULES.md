# Project rules

These rules do not bend. Code comments and tests refer to them by number (for example "rule 4").
`BACKEND_SCHEMA.md` wins on names and values, and `TRD.md` wins on behaviour.

1. **No automatic sending.** No code path may send email or messages. Drafts are shown and copied. A Gmail connector, if ever added, creates drafts only.
2. **The model reads and writes. Code decides.** Routing, required fields, escalation, the safety keyword net and every draft check are plain code with unit tests. A model never decides that something is safe to send.
3. **Use the exact strings in `BACKEND_SCHEMA.md`.** Statuses, intents, reason codes and check codes are not invented or renamed. A test keeps the enums in code and the database `CHECK` constraints in step.
4. **No message or draft text in logs or audit events.** Ids, stage names, timings, route and reason codes only. A test covers this.
5. **Inquiry text and retrieved documents are untrusted.** Model output is rendered as text, never as HTML, and is never used to build paths, queries or URLs.
6. **Never answer from nowhere.** If the knowledge base declines or returns no sources, the inquiry is escalated with `NOT_IN_KNOWLEDGE_BASE`. Nothing is drafted from model memory.
7. **Synthetic data is labelled** in the UI and the README ("Demo data. All customers and messages are invented."). Phones are 555-01xx and emails are at example.com.

## Working conventions

- Tests come first for anything that is plain code. `FakeLLM` and `FakeKB` keep the test suite free of a model, network or GPU.
- Model behaviour is measured by the evaluation, not asserted in unit tests.
- The held-out set is never tuned on: it is run once and the number is reported as it comes out.
- Decisions that the documents do not cover are recorded, with the reason, in `DECISIONS.md`.
- Small commits, one per task. No `.env`, database file, secret or real data is ever committed.
- One branch and one pull request per phase from Phase 2, with CI green before merging (D-025).
