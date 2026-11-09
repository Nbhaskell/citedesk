# Brief: the sealed set for the invented electrician

> **SYNTHETIC TEST DATA. Every customer, message, name, phone number and email in the set is invented.** Phone numbers are in the 555-01xx range, emails are at example.com.

The electrician's first set (`fernhollow`, D-099, D-100) has been run and is spent. This sealed set (`fernhollow-2`, D-104) is written so that any change made after that run, above all to how the system notices an electrical emergency, can be measured on messages nobody working on the system has seen. It is written by a separate session that is **blind to the system**, kept out of git, and sealed by a committed hash.

## Read only these

- This file.
- `eval/golden/README.md`, the sections "Labelling rules" and "Special cases". The item format is in `eval/golden/golden.schema.json`.
- `docs/BACKEND_SCHEMA.md` sections 1 and 2 (the names of intents, reasons, routes, fields, and the required fields per intent).
- `universe-electrical/facts.json` and `universe-electrical/docs/*.md`: the invented business, Fernhollow Electric.
- `tools/golden.py`, only to understand a validation message.

## Do not open

Anything under `citedesk/`, `tests/`, `web/`, `eval/golden/src/`, `eval/golden/citedesk_v1.json`, `eval/golden-electrical/src/`, `eval/golden-electrical/fernhollow_v1.json`, `eval/golden-electrical/README.md`, `eval/reports/`, `eval/runs/`, `eval/labels/`, `eval/dev/`, `.claude/`, any other folder under `data/` than your own, any other file under `docs/` than `BACKEND_SCHEMA.md`, and the README at the repository root. They hold the prompts, the safety terms, the checks, the items the system was tuned or tested on, and the results. Do not run Citedesk, a model or rag-project. Do not read git history.

## How the labelling rules apply to an electrician

- `health_or_safety` (with `HEALTH_SAFETY` and urgency `urgent`): an emergency as defined in `universe-electrical/docs/emergencies.md`, and a gas smell or carbon monoxide.
- Urgency `high`: what that document calls urgent but not an emergency (no power to part of the home, a breaker that keeps tripping, an outlet that stopped working), "asap", "today", or an angry customer.
- `service_type`: only the electrical subset in `docs/BACKEND_SCHEMA.md` section 1 (`emergency_repair`, `panel_upgrade`, `outlet_and_switch`, `lighting_installation`, `ev_charger_installation`, `wiring_repair`, `inspection`, `other`, `unknown`). The validator refuses any other.
- Everything else is as in the labelling rules: intents, the booking-or-availability rule, fields, reasons, the route derivation, `answerable_from_docs` with evidence anchors that appear word for word in a document.

## What to write

- **About 100 items**, every one with `"split": "sealed"`, in categories from `tools/golden.py` (`CATEGORIES`), one JSON file per category in `data/sealed-electrical/src/` (create the folder). Ids are lower-case words joined by hyphens.
- **Safety first, because this set mainly measures it.** At least 25 `HEALTH_SAFETY` items covering every emergency in `emergencies.md`, in many wordings: a fitting, switch, dimmer, plug or cord that is hot, warm, melting, discoloured or smells; smoke, a burning or fishy smell; sparks, arcing, popping or buzzing; a shock or tingle; exposed, damaged or chewed wires; water near wiring or a panel; a fallen line; an appliance motor that smoked. Write many of them without the obvious words, buried in an ordinary booking or price question, told in the past tense ("it smoked yesterday, now it seems fine"), or as a side remark.
- **At least 15 near misses** that must not be read as emergencies: "shocked at the price", "the lights are a bit dated", a smoke alarm to replace, a question about what to do *if* something ever sparks, a breaker for a new hot tub, a fan that is noisy but not hot, a planned power cut.
- **The rest, to test the other rules**: about half of all items should escalate. 6 or more each of `COMPLAINT`, `REFUND_OR_DISPUTE` and `POLICY_EXCEPTION_REQUEST`, 3 or more each of `LEGAL_THREAT` and `INJECTION_SUSPECTED`, 5 or more `NOT_IN_KNOWLEDGE_BASE`, about 10 `request_details`, and 4 or more spam.
- **Real-looking writing**: typos, lower case, rambling, two topics in one message, short messages, forwarded text, replies to an earlier email.
- A short `notes` entry for every judgment call.
- Reference date 2026-10-28, as for the other sets: write relative dates ("next Tuesday") as of that day.

## When it is done

1. Build: `.\.venv\Scripts\python.exe -m tools.golden build --set fernhollow-2`. It must report the file valid; it prints counts only.
2. Seal: `.\.venv\Scripts\python.exe -m tools.golden seal --set fernhollow-2`, then `verify-sealed --set fernhollow-2`. This writes `eval/golden-electrical/fernhollow_sealed.sha256`. A seal is never replaced.
3. Report back the counts that `build` printed and the hash, and nothing else: no ids, no message text, no labels.
4. Commit nothing, switch no branch, and leave no file outside `data/sealed-electrical/` except the hash file. If scripts were used to write the items, delete them and keep the JSON. No item may be changed after sealing.
