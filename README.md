# Citedesk

> **Work in progress.** This project is under construction and is not ready to use.

> **Demo data. All customers and messages are invented.** Every name, email address, phone number and inquiry in this repository is synthetic, from an invented plumbing company. There is no real customer data here.

Citedesk is an AI review desk for customer inquiries at a small service business. It reads an incoming message, works out what the customer wants, drafts a reply from the business's own documents, checks the draft in code, and queues it for a person to approve.

**Nothing is ever sent automatically.** Drafts are shown for a person to copy.

## Status

Phases 0 to 3 are built: repository and tooling, the invented business with its labelled test messages, the data layer, and intake with screening. The API accepts inquiries (one at a time or as a JSONL or CSV file), masks card and Social Security numbers before storing them, archives spam, and escalates suspected prompt injection. Nothing reads a message with a model yet, and no reply is drafted. See `docs/IMPLEMENTATION_PLAN.md` for the build order.

## Run it (Windows, PowerShell)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m citedesk
```

Then open <http://127.0.0.1:8100/api/status>.

Run the checks:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
```

## Known weaknesses

What follows is what the tests and the measured runs show, with the file that shows it. Numbers come from `eval/reports/README.md`; the evaluation data is invented and one person labelled it. No judge has scored the drafts; the only look at their quality was a manual read of 30 of them (D-049).

**Prompt injection is only partly stopped.** There are three lines of defence: screening patterns (plain code), the draft checks (plain code), and a person who reads every draft. Nothing is sent automatically.
- Screening flagged all 6 injection items in the tuned set, which its patterns were written with in view. On the held-out set it flagged 1 of 4; the other 3 reached a reviewer as ordinary replies.
- Five invented messages in new words (a role-play as the owner, a fake notice, a request to paste the model's guidelines, a quoted forward, a request to add a sentence) are not flagged by screening (`tests/test_injection_end_to_end.py`). Run once each through the real model, three were not obeyed, one was obeyed and blocked by the commitment check, and one ("end your reply with the sentence ...") was obeyed and reached the reviewer as a ready draft. Five messages and one run each is a check, not a rate.
- The draft checks compare phrases and values. The commitment check knows "I will credit" but not "I will apply a credit", and an invented perk with no figure in it passes every check.

**Understanding and routing are weaker on unseen messages.** On the held-out set (76 items) primary-intent accuracy was 69.8% against a target of 85%, route accuracy 68.9%, and policy-exception requests were escalated 1 time in 6. All 3 spam items in the first pass were escalated and none was archived. Health-and-safety messages were escalated in all 12 cases, which is a small count.

**Failures are handled, and each leaves the inquiry where a person can find it** (`tests/test_failure_paths.py`). If the model is offline or gives invalid JSON twice, the inquiry becomes `failed` at its stage and Retry resumes there. If the knowledge base is offline, it fails at retrieval and nothing is drafted without sources. If the database is locked, a write is refused with a generic 500 and a request id, nothing is half stored, reads still work, and the background worker carries on once the lock clears. An inquiry that was accepted is never lost.

**Single user, one machine.** There is no authentication, and the server listens on `127.0.0.1` only. The size limit (413) and the rate limit (429, 300 requests a minute for new inquiries and imports) are checked inside the one process, for all callers together, and the rate counter starts again when the server restarts.

**Logs hold ids, codes and type names, not text.** The server writes no access log (its lines would carry search text), and an unexpected error is answered by the app so the server never logs a traceback (`tests/test_hardening_logs.py`). Dependencies were audited on 2026-10-29 with `pip-audit` and `npm audit` and no known vulnerabilities were reported; the audit is a point in time.

## Documentation

Planning documents are in `docs/`. Start with `docs/PRD.md`, then `docs/TRD.md`.
