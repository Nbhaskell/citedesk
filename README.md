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

## Documentation

Planning documents are in `docs/`. Start with `docs/PRD.md`, then `docs/TRD.md`.
