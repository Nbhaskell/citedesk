# Decisions

Decisions the planning documents do not cover. Each entry says what was chosen and why. Newest last.

## Phase 0

### D-001. Defaults for settings the TRD lists without a value
`docs/TRD.md` section 7 names `CITEDESK_DB_PATH`, `OLLAMA_URL`, `SPAM_THRESHOLD` and `DRAFT_MAX_WORDS` but gives no defaults. Chosen:

| Setting | Default | Why |
|---|---|---|
| `CITEDESK_DB_PATH` | `data/citedesk.db` | `data/` is git-ignored, so the database file cannot be committed by accident |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama's own default address |
| `SPAM_THRESHOLD` | `0.8` | **Provisional.** Nothing exists to measure yet. Revisit in Phase 3 using the `tuned` split only |
| `DRAFT_MAX_WORDS` | `200` | **Provisional.** Revisit in Phase 5 after reading drafts |

### D-002. `/api/status` in Phase 0 reports only what exists
`docs/TRD.md` section 6 describes `/api/status` as model, knowledge base and database health plus the synthetic-data flag. In Phase 0 none of those components exist, so the endpoint returns `status`, `app`, `version`, `synthetic_data`, the configured model name, and a `components` block where each of `database`, `model` and `knowledge_base` is `"not_checked"`. It never reports `ok` for something it did not check. Real checks arrive with the database (Phase 2), the model (Phase 4) and the knowledge base (Phase 5). The response omits URLs and file paths.

### D-003. The server's bind address is a constant, not a setting
`docs/TRD.md` section 8 requires binding to `127.0.0.1` because v1 has no authentication. `python -m citedesk` passes `127.0.0.1` as a constant, and a test checks that no environment variable changes it. Only the port is configurable.

### D-004. Settings use `pydantic-settings`
It reads the environment and `.env`, validates types and ranges, and keeps the exact variable names from the TRD through field aliases. A test checks that `.env.example` lists exactly the settings in code and that its values equal the defaults, so the two cannot drift.

### D-005. Type checker: mypy (strict) on `citedesk/`
The plan allows mypy or pyright. mypy installs with pip, so the toolchain stays pip-only.

### D-006. Lint rules and formatter scope
Ruff lint rules: `E, F, I, B, UP, SIM, S` (the `S` security rules are on; tests may use `assert`). Line length 100. `docs/` and `web/` are excluded from ruff because recent ruff versions also format Markdown code blocks, and the planning documents should not be rewritten by a formatter.

### D-007. Lock files are `pip freeze` output
No lock tool is installed, so `requirements.lock` is the `pip freeze` of a clean runtime-only environment and `requirements-dev.lock` is the freeze of the development environment (runtime plus dev tools). They have no hashes. Regenerate both when `pyproject.toml` dependencies change. The dev lock was made on Windows and includes `colorama`, which is harmless on Linux.

### D-008. CI is tests and lint only
`.github/workflows/ci.yml` runs `ruff check`, `ruff format --check`, `mypy` and `pytest` on Ubuntu with Python 3.13, installing from `requirements-dev.lock`. It does not run the model, the knowledge base or any evaluation. The secret scan runs in pre-commit, as the plan says. **Not yet run on GitHub:** there is no remote yet, so "CI is green" is unverified until the repo is pushed.

### D-009. Secret scan: gitleaks through pre-commit
`.pre-commit-config.yaml` runs the `gitleaks` hook (pinned to `v8.30.1`) on staged files, using the default gitleaks ruleset in `.gitleaks.toml` with no allowlist. It was checked against a deliberately fake token and blocked it. Enable it on a fresh clone with `pre-commit install`.

### D-010. Line endings: LF
`.gitattributes` sets `* text=auto eol=lf` so files are the same on Windows and in CI.

### D-011. `web/` is not scaffolded in Phase 0
No Phase 0 task covers the web app, and the UI is built in Phase 6. `web/` exists as an empty directory so the layout matches `docs/TRD.md` section 3. The `run web` command is filled in when the app exists. The dev server will use a Vite proxy for `/api` to `127.0.0.1:8100` rather than enabling CORS (to be confirmed in Phase 6).

### D-012. `CLAUDE.md` is not tracked yet
`CLAUDE.md`, `CLAUDE.local.md` and `.claude/` are in `.gitignore`. They are assistant-instruction files, and whether to publish them is the owner's call. To track `CLAUDE.md`, remove it from `.gitignore`.

### D-013. Test client dependency
`fastapi.testclient` (Starlette) warns that `httpx` is deprecated for the test client and suggests a package called `httpx2`. It was not adopted: it was not possible to confirm who publishes it, and the warning is harmless today. Revisit if the warning becomes an error.

### D-014. Python version
`pyproject.toml` pins `requires-python = ">=3.13,<3.14"`, matching the stack in `CLAUDE.md`. The machine's default `python` is 3.14, so commands use `py -3.13` to create the virtual environment.

### D-015. Package metadata and install
`pip install -e . --no-deps` after `pip install -r requirements-dev.lock` makes the package importable while keeping the locked versions authoritative.
