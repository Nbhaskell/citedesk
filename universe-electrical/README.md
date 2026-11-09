# universe-electrical: the second invented business

> **SYNTHETIC TEST DATA. All customers, staff, prices and messages are invented.** Fernhollow Electric does not exist. Phone numbers are in the 555-01xx range and emails are at example.com.

This folder holds an invented residential electrician in the same invented town as Kestrel Hollow Plumbing (`universe/`). It exists to test whether Citedesk works for a trade other than the one it was built for (D-097, D-098). The code was not changed for it beyond the trade profile (`citedesk/trade.py`).

| Path | What it is |
|---|---|
| `facts.json` | The single source of truth: prices, hours, policies, staff, service area. It names its trade (`business.trade`: `electrical`). |
| `docs/` | The knowledge-base documents, generated from `facts.json` by `tools/kb_electrical.py`. |
| `manifest.json` | Hashes of the fact sheet and each document, and how they were generated. |

There is no labelled set for this business yet. It is to be written by a separate session that is given the labelling rules and this fact sheet, not the prompts or any results (D-097, phase C).

## Rebuild and check

Fix the generator, never the generated files.

```powershell
.\.venv\Scripts\python.exe -m tools.generate_kb_docs --universe universe-electrical
.\.venv\Scripts\python.exe -m tools.check_consistency --universe universe-electrical
```

To run Citedesk against this business, point `BUSINESS_FACTS_PATH` at `universe-electrical/facts.json` and start rag-project with `RAG_DOCS_DIR` set to `universe-electrical/docs` and its own `RAG_DB_DIR`.
