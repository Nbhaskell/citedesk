# Golden set for the invented electrician

> **SYNTHETIC TEST DATA. Every customer, message, name, phone number and email here is invented.** Phone numbers are in the 555-01xx range, emails are at example.com.

Labelled inquiries for Fernhollow Electric, the invented electrician in `universe-electrical/`. They test whether Citedesk, built and tuned for a plumber, works unchanged for another trade (D-097 to D-099).

| Path | What it is |
|---|---|
| `src/*.json` | The items, hand-written, one file per category. Edit these. |
| `fernhollow_v1.json` | Built from `src/`: `{header, items}`. Never edit by hand. |

```powershell
.\.venv\Scripts\python.exe -m tools.golden build --set fernhollow      # merge src/ into fernhollow_v1.json (refuses if anything is invalid)
.\.venv\Scripts\python.exe -m tools.golden validate --set fernhollow   # check the committed file; prints counts
```

Every item has `"split": "heldout"`: this set is never used to change the system. It is run once (D-097, phase D).

## Brief for the session that writes it

This set is written by a session that is **blind to the system**: it sees the labelling rules and the electrician's facts, and nothing that shows how Citedesk reads, routes or drafts. Keep it that way.

**Read only these.**
- This file.
- The labelling rules in `eval/golden/README.md` (the sections "Labelling rules" and "Special cases"; the item format is in `eval/golden/golden.schema.json`).
- `docs/BACKEND_SCHEMA.md` sections 1 and 2 (the names of intents, reasons, routes, fields, and the required fields per intent).
- `universe-electrical/facts.json` and `universe-electrical/docs/*.md`.
- `tools/golden.py`, only to understand a validation message.

**Do not open** anything under `citedesk/`, `tests/`, `eval/golden/src/`, `eval/golden/citedesk_v1.json`, `eval/reports/`, `eval/runs/`, `eval/labels/`, `data/`, `docs/DECISIONS.md`, `docs/TRD.md` or the README at the repository root. They hold the prompts, the safety terms, the plumbing items the system was tuned on, and the results. Do not run Citedesk, a model or rag-project.

**How the labelling rules apply to an electrician.**
- `health_or_safety` (with `HEALTH_SAFETY` and urgency `urgent`): an emergency as defined in `universe-electrical/docs/emergencies.md`, and a gas smell or carbon monoxide.
- Urgency `high`: what that document calls urgent but not an emergency (no power to part of the home, a breaker that keeps tripping, an outlet that stopped working), "asap", "today", or an angry customer.
- `service_type`: only the electrical subset in `docs/BACKEND_SCHEMA.md` section 1 (`emergency_repair`, `panel_upgrade`, `outlet_and_switch`, `lighting_installation`, `ev_charger_installation`, `wiring_repair`, `inspection`, `other`, `unknown`). The validator refuses any other.
- Everything else is as in the labelling rules: intents, the booking-or-availability rule, fields, reasons, the route derivation, `answerable_from_docs` with evidence anchors that appear word for word in a document.

**What to write.**
- About 80 items, in categories from `tools/golden.py` (`CATEGORIES`), with ids in lower-case words joined by hyphens.
- A mix close to the plumbing held-out split, so per-reason numbers rest on more than a handful: about half should escalate, with at least 10 `HEALTH_SAFETY` (several of them buried in an ordinary request or worded without the obvious words), 6 or more each of `COMPLAINT`, `REFUND_OR_DISPUTE` and `POLICY_EXCEPTION_REQUEST`, 3 or more each of `LEGAL_THREAT` and `INJECTION_SUSPECTED`, 4 or more `NOT_IN_KNOWLEDGE_BASE`, about 10 `request_details`, and 3 or more spam. Include near misses that only look like an emergency, an attack or sensitive data ("I was shocked at the quote", "ignore my earlier message", a smoke alarm replacement).
- Questions an electrician's customers actually ask: panels and fuse boxes, outlets that stopped working, flickering lights, GFCI outlets that trip, EV chargers, permits, inspections for a house sale, ceiling fans, power cuts on the whole street, and things the business does not do (plumbing, solar, security cameras).
- Real-looking writing: typos, lower case, rambling, two topics in one message, short messages, forwarded text.
- A short `notes` entry for every judgment call.

**When it is done.** `build --set fernhollow` must report the file valid. Commit `src/` and `fernhollow_v1.json` on a branch of their own, with a commit message and this README updated with the counts. Do not push. No item may be edited after any system has read it.
