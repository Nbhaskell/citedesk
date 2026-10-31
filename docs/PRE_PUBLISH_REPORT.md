# Pre-publish checklist report

Run on 2026-10-30 against branch `phase-9-documentation`, before the repository is made public. Each
item is PASS, FAIL or NOT CHECKED, with the evidence. FAILs come first.

## FAIL

| Item | Evidence | Fix |
|---|---|---|
| A short description and topics are set on the repository | `gh repo view` shows an empty description and no topics. The repository is also still private. | Before going public: `gh repo edit --description "..." --add-topic ...`, then change the visibility. Both change the remote, so they wait for the owner. |

## PASS

| Item | Evidence |
|---|---|
| Secrets in history and the working tree | gitleaks v8.30.1 (the project's pre-commit hook, no allowlist): `gitleaks git` scanned 102 commits (2.97 MB), no leaks; `gitleaks dir` scanned the working tree including ignored and untracked files (73.6 MB), no leaks. `.env` is git-ignored and not tracked; `.env.example` holds placeholders only. |
| Screenshots hold no keys, emails or paths | Three of 66 viewed (`settings-checked`, `detail-review`, the README image): emails are `example.com`, phones are 555-01xx, no file paths or tokens on screen, and every screen carries the "Demo data" footer. All 66 come from one scripted capture of invented data. |
| Personal data and local traces | `git grep` over tracked files for the username, home paths and personal name finds only the public GitHub username in README links. Every commit's author email is the GitHub no-reply address. Emails not at `example.com` appear only in tests that check the validators reject them (`tests/test_golden.py`, `tests/test_kb_docs.py`, `tests/test_checks.py`); phone numbers outside 555-01xx likewise (`tests/test_golden.py`). `data/`, `.venv/`, `node_modules/`, `build/`, `eval/runs/` and `CLAUDE.md` are git-ignored; no build output or egg-info is tracked. |
| A LICENSE file exists and matches the README | `LICENSE` is the MIT licence (copyright 2026 Nathan Haskell, the name on every commit); the README's Licence section says MIT. Added after the first run of this checklist, at the owner's choice. All runtime Python dependencies are MIT, BSD, Apache-2.0 or PSF-2.0, so none conflicts. |
| Third-party data | None. The invented business's README says no names, wording or prices were copied from a real company. |
| Dependencies | Lock files are present. `pip-audit` on `requirements.lock` and `requirements-dev.lock`: no known vulnerabilities. `npm audit`: 0 vulnerabilities in 480 packages. Runtime Python licences (`pip-licenses` over `requirements.lock`): MIT, BSD-3-Clause, Apache-2.0 and PSF-2.0 only, none conflicting. |
| Synthetic data is labelled | README banner; the web app's footer and Settings screen ("Demo data. All customers and messages are invented."); `universe/README.md`; the screenshots page. The eight knowledge-base documents in `universe/docs/` are **not** labelled inside the files: they are generated text that the knowledge base indexes, and a label inside them would change what is indexed and the system that was measured (D-067). The label sits in the folder's README beside them. Fictional names use 555-01xx phones and `example.com` emails. |
| Claims match evidence | Eight README numbers traced to saved report files: 83.5% and 69.8% intent, 12 of 12 safety, 16.3 s median, 90.7% fields, 43 of 76 reaching a ready draft, 0 of 6 caught (interval 0 to 0.46) and 37 s review time. Tuned against held-out is stated throughout, with sample sizes; limits and known failures are in "What the numbers do not say" and "Where it goes wrong". The time-saved section labels every assumption and says no saving was measured. No claim of production use or customers. |
| A stranger can run it | Fresh clone into an empty folder, README commands as written (PowerShell, Windows 11): install from the lock file, **2093 tests pass**, ruff and mypy clean; in `web/`: `npm ci`, lint, typecheck, test and build pass. Demo: rag-project indexed the clone's documents (8 files, 83 chunks, as in every evaluation run), the API started from the clone, `tools.import_inquiries --limit 3` created 3 inquiries and all 3 reached `needs_review`, and the web app served on 5174 and proxied the API. CI passes on every pushed branch. Relative links in the README, docs and reports resolve (checked by script). |
| Repo hygiene | Largest tracked files: the walkthrough image (1 MB), `package-lock.json` and the golden set (240 KB). No binaries beyond the screenshots. |
| Hardening for a hosted deployment | Not applicable: nothing is hosted, the server listens on `127.0.0.1` only. Even so: intake has a size and a rate limit, logs hold no message text, model output is rendered as text, and prompt-injection behaviour is tested with its known weaknesses written in the README. |
| First impression | The README opens with what it does and why it can be trusted, shows the review screen, reports the missed target and the reviewer trial, and includes empty, error and refusal states in the screenshots. |

## NOT CHECKED

- Licences of the JavaScript dependencies (only the Python runtime licences were listed).
- All 66 screenshots individually (three viewed).
- Running the stack on macOS or Linux (CI runs the tests on Linux only; the README says so).
- The CI badge against `main` after this branch merges, and the public rendering of README links and images (the repository is private).
- Docker Compose: not provided (D-067).

## The three most important fixes

1. Set the repository description and topics, then decide on visibility.
2. Check the JavaScript dependency licences.
3. Re-run `pip-audit` and `npm audit` on the day the repository goes public: they are point-in-time results.
