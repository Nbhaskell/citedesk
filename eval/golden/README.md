# Golden set

> **SYNTHETIC TEST DATA. Every customer, message, name, phone number and email here is invented.** Phone numbers are in the 555-01xx range, emails are at example.com.

Labelled inquiries for the invented plumbing company in `universe/`. They are the ground truth the evaluation measures against.

| Path | What it is |
|---|---|
| `src/*.json` | The items, hand-written, one file per category. Edit these. |
| `citedesk_v1.json` | Built from `src/`: `{header, items}`. Never edit by hand. |
| `golden.schema.json` | JSON Schema, generated from the models in `tools/golden.py`. |

```powershell
.\.venv\Scripts\python.exe -m tools.golden build      # merge src/ into citedesk_v1.json (refuses if anything is invalid)
.\.venv\Scripts\python.exe -m tools.golden validate   # check the committed file; prints counts per intent, category, route
.\.venv\Scripts\python.exe -m tools.golden schema     # regenerate golden.schema.json
```

The validator checks the schema; that `expected_route` and `should_escalate` agree with the routing rules applied to the labels; that every `evidence` anchor really appears in the named document; that the file's document hash matches the current documents; and the synthetic-data rules. If the documents are regenerated, `validate` fails until the anchors are re-checked and `build` is run.

## Who wrote it, and what that means

Written by an AI model (Claude), by hand, in one pass per category, from the same fact sheet and documents the system uses. So the set is **unseen but not blind**: its wording and its idea of "messy" come from the same process that wrote the knowledge base. There is no generator and no seed; the committed files are the data. Real customers write in ways this set does not.

## Splits

- `tuned`: items the system may be adjusted against.
- `heldout`: written **after** the first working prototype, in new wording, and run **once** before any tuning. Not written yet. Never tune on it. Once a held-out run has driven a change, that set is spent and a new one is written.

## Labelling rules

**Reference date.** Messages are written as if received on 2026-10-28 (the header's `reference_date`).

**Intents.** `intents` lists everything the customer asks for; `primary_intent` is what they most want answered.
- Opening hours, service area, and what the business does: `service_question`. Terms (warranty, cancelling, payment, access, discounts): `policy_question`. Whether someone is free at a time: `availability_question`.
- Asking for a visit: `booking_request`. Moving a visit: `booking_change`. Cancelling: `cancellation`.
- Gas smell, carbon monoxide, flooding, a burst pipe or sewage backing up: `health_or_safety`, always with reason `HEALTH_SAFETY` and urgency `urgent`.
- Marketing and bulk offers: `spam`. A real question inside an injection attempt keeps its real intent.

**Urgency.** `urgent`: an emergency as defined in `universe/docs/emergencies.md`. `high`: a problem that cannot wait (no hot water, "asap", "today"), or an angry customer. `normal`: the default. `low`: no time pressure or pure information.

**Fields.** Every item has `service_type`, `start_date`, `property_type`, `address_area`; null means the customer did not say. `service_type` is labelled whenever the customer indicates the work, even for a price question. A date is ISO only when it is unambiguous: a month and day, or a weekday that agrees with a stated date ("Tuesday the 3rd of November"). Relative dates ("next Tuesday", "this week", "tomorrow") are null. A neighbourhood is written as the customer wrote it.

**Escalation reasons.** `expected_reason_codes` lists every reason that applies at the point the route is decided. `COMPLAINT` for a complaint about service received. `REFUND_OR_DISPUTE` for a request for money back or a disputed charge. `LEGAL_THREAT` for a lawyer, a lawsuit or a licensing-board report. `POLICY_EXCEPTION_REQUEST` for a discount, a waived fee, a price match, cash with no invoice, or any exception only the owner can grant. `INJECTION_SUSPECTED` when the text tries to instruct the system. `LOW_CONFIDENCE` only for messages too unclear to classify (model-dependent; each such item says so in `notes`). `NOT_IN_KNOWLEDGE_BASE` only when the draft path is reached (no other reason, no missing details) and the question is not in the documents.

**Route.** Derived, then checked: spam only, then archive; any reason other than `NOT_IN_KNOWLEDGE_BASE`, then escalate; a missing required field for any of the intents, then `request_details`; `NOT_IN_KNOWLEDGE_BASE`, then escalate; otherwise `draft_reply`. Required fields per intent are in `docs/BACKEND_SCHEMA.md` section 2. v1 cannot match a sender to an existing booking (there is no customer or booking table), so `booking_change` and `cancellation` without a `booking_reference` always get `request_details`.

**`answerable_from_docs`.** True when the documents address what the customer asked, whether or not the item is escalated (a gas-smell message is answerable: the documents say what to do; a complaint is not). For a booking request, true means the documents say what is needed to book. Then `evidence` lists one or more `{file, anchor}`. False items have no evidence.

**Special cases.**
- `near_miss` items look like an attack or sensitive data but are not (for example "ignore my earlier message"). They must not be escalated for that reason.
- `contains_sensitive_data` is true when the message includes a card number or government ID.
- `injection` items record what the customer genuinely asks. Some are subtle and a pattern detector may miss them; the label is what should happen, not what a detector will do.

## Known gaps

- **Small counts.** 135 items in total, and fewer per label: `HEALTH_SAFETY` 8, `LEGAL_THREAT` 2, `LOW_CONFIDENCE` 1, `REFUND_OR_DISPUTE` 5, `cancellation` as primary intent 3, `availability_question` 3. A per-reason precision or recall from so few items is a rough guide at best. For example, 0 misses out of 8 safety items is compatible with a true miss rate of up to roughly one in three.
- **The mix is not a real inbox.** 45 of 135 items (33%) are expected to escalate and 6 are spam, so that every rule is exercised. Overall accuracy on this set says nothing about the share of escalations or spam a real business would see.
- **Some labels are judgment calls.** Notes on borderline items say so (a ceiling leak of unknown severity, a sewer smell with nothing coming up, a cafe versus a home). `LOW_CONFIDENCE` depends on the model reporting low confidence and is the label most likely to disagree with a run.
- **A tension in the fact sheet.** It prices water heater replacement but also says the business does not do gas line or gas appliance work, so a gas-fired heater is unclear. `unanswerable-gas-water-heater-swap` records it as unanswerable. The owner would need to settle it; if the fact sheet changes, the documents are regenerated and this item is revisited.
- **No rule for commercial property.** `oos-dental-office-booking` has every booking field, so by the current rules the route is `draft_reply`, and the correct reply is a refusal. Phase 4 may add a routing rule.
- The writing is cleaner than real customer writing and the same hand wrote all of it. About 17 of 135 messages contain a real misspelling and about 44 start in lower case; the median message is 25 words. Real inquiries have more typos, more rambling, more attachments and more messages that mix two unrelated topics.
- Single labeller; no second pair of eyes on any label.
- Labels follow the rules above, which are a judgment, not a fact. Where a rule is arguable (for example, hours as `service_question`), it is stated here so it can be challenged.
