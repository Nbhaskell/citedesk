# Brief: the third sealed set for the invented plumber

> **SYNTHETIC TEST DATA. Every customer, message, name, phone number and email in the set is invented.** Phone numbers are in the 555-01xx range, emails are at example.com.

The first and second sealed sets (D-087, D-108) have been run and are spent. This third one (`kestrel-3`, D-111) is written so that any change made after the second run can be measured on messages nobody working on the system has seen. It is written by a separate session that is **blind to the system**, kept out of git, and sealed by a committed hash.

## Read only these

- This file.
- `eval/golden/README.md`, the sections "Labelling rules" and "Special cases". The item format is in `eval/golden/golden.schema.json`.
- `docs/BACKEND_SCHEMA.md` sections 1 and 2 (the names of intents, reasons, routes, fields, and the required fields per intent).
- `universe/facts.json` and `universe/docs/*.md`: the invented business, Kestrel Hollow Plumbing.
- `tools/golden.py`, only to understand a validation message.

## Do not open

Anything under `citedesk/`, `tests/`, `web/`, `eval/golden/src/`, `eval/golden/citedesk_v1.json`, `eval/golden/SEALED_V2_BRIEF.md`, `eval/golden-electrical/`, `eval/reports/`, `eval/runs/`, `eval/labels/`, `eval/dev/`, any ledger under `eval/`, `.claude/`, any other folder under `data/` than your own, any other file under `docs/` than `BACKEND_SCHEMA.md`, and the README at the repository root. They hold the prompts, the safety terms, the checks, the items the system was tuned or tested on, and the results. Do not read notes, transcripts or hand-over files of other sessions. Do not run Citedesk, a model or rag-project. Do not read git history.

## What to write

- **About 120 items**, every one with `"split": "sealed"`, in categories from `tools/golden.py` (`CATEGORIES`), one JSON file per category in `data/sealed-3/src/` (create the folder). Ids are lower-case words joined by hyphens.
- **A mix built to test every rule**: about half should escalate. At least 15 `HEALTH_SAFETY` (gas, carbon monoxide, flooding, sewage, no water and the other emergencies in `universe/docs/emergencies.md`; several buried in an ordinary request or worded without the obvious words), 8 or more each of `COMPLAINT`, `REFUND_OR_DISPUTE` and `POLICY_EXCEPTION_REQUEST`, 5 or more each of `LEGAL_THREAT` and `INJECTION_SUSPECTED`, 6 or more `NOT_IN_KNOWLEDGE_BASE`, about 15 `request_details`, and 8 or more spam, some of them politely worded.
- **At least 6 messages with two or more intents**, where one of them decides the route.
- **Near misses**, at least 10: messages that only look like an emergency, an attack, spam or sensitive data.
- **Booking or availability**: follow the rule in the labelling rules exactly; include several messages on each side of it.
- **Real-looking writing**: typos, lower case, rambling, very short messages, forwarded text, replies to an earlier email, a few non-native phrasings.
- A short `notes` entry for every judgment call.
- Reference date 2026-10-28, as for the other sets: write relative dates ("next Tuesday") as of that day.

## When it is done

1. Build: `.\.venv\Scripts\python.exe -m tools.golden build --set kestrel-3`. It must report the file valid; it prints counts only.
2. Seal: `.\.venv\Scripts\python.exe -m tools.golden seal --set kestrel-3`, then `verify-sealed --set kestrel-3`. This writes `eval/golden/citedesk_sealed_v3.sha256`. A seal is never replaced.
3. Report back the counts that `build` printed and the hash, and nothing else: no ids, no message text, no labels.
4. Commit nothing, switch no branch, and leave no file outside `data/sealed-3/` except the hash file. If scripts were used to write the items, delete them and keep the JSON. No item may be changed after sealing.
