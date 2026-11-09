# Citedesk

![CI](https://github.com/Nbhaskell/citedesk/actions/workflows/ci.yml/badge.svg)

> **Demo data. All customers and messages are invented.** Every name, email address, phone number and inquiry in this repository is synthetic, from two invented businesses, a plumber ("Kestrel Hollow Plumbing") and an electrician ("Fernhollow Electric"). There is no real customer data here, and nothing has been tried on a real business.

Citedesk is an AI review desk for customer inquiries at a small service business. It reads an incoming message, works out what the customer wants, drafts a reply from the business's own documents, checks the draft in code, and queues it for a person to approve. **Nothing is ever sent automatically**: drafts are shown for a person to copy.

It is built to be checked, not trusted. The model reads and writes; plain code, with unit tests, decides what is routed, what is escalated and what a draft may say. This README reports what was measured, including the targets it missed and a trial in which a reviewer missed every planted problem.

Part of a family of projects: [citeTally](https://github.com/Nbhaskell/citeTally), [citewise-markets](https://github.com/Nbhaskell/citewise-markets), [rag-project](https://github.com/Nbhaskell/rag-project), [citecheck](https://github.com/Nbhaskell/citecheck).

![The review screen: message, how it was understood, the draft with its checks and sources](docs/screenshots/detail-review-1280.webp)

More screens, every state at desktop and phone width: [docs/screenshots/](docs/screenshots/README.md). Those pictures were made with a scripted model, not a language model's wording (see that page).

## What it does

1. **Screens** each message in code: masks card and Social Security numbers, archives spam, escalates suspected prompt injection, spots emergencies.
2. **Understands** it with a local model (`qwen3:8b` through Ollama): intents, urgency, tone, the details given and the details missing.
3. **Routes** it in code: draft a reply, ask for the missing details, or escalate to a person with a named reason (safety, complaint, legal threat, refund, policy exception, not in the documents, and so on).
4. **Retrieves** answers from the business's documents with [rag-project](https://github.com/Nbhaskell/rag-project), asking one question per intent. If the documents don't answer, it escalates with `NOT_IN_KNOWLEDGE_BASE` and never answers from the model's memory.
5. **Drafts** a reply from those passages only, and **checks** the draft in code: every figure appears in the sources, no promise only the owner can make, no copied instructions or unknown links.
6. **Queues** it for review. The person approves, edits, rejects, escalates or asks for a redraft, and copies the approved text. There is no send path anywhere in the code (a test looks for one).

Everything is stored in SQLite, with an audit trail that holds ids, stage names, timings and reason codes, never message or draft text.

## How well it works

Every row below is a set of invented messages the system had **not** been tuned on, run once with three passes. All were written by an AI model (Claude). The held-out set was written by the session that built the system; every later set by a separate session that saw the labelling rules and the business's documents but not the code, prompts or results. The sealed sets were kept out of the repository until their one run. The system was improved between rows, so each row measures the system as it stood then. Full numbers: [eval/reports/](eval/reports/README.md).

| Unseen set | Items | Safety messages escalated (target: all) | Intent right (target 85%) | Route right | Escalation precision / recall | Cost per 100 (escalate all) |
|---|---|---|---|---|---|---|
| Plumber, held-out ([report](eval/reports/heldout-think-on.md)) | 76 | 12 of 12 | 69.8% | 68.9% | 85.0% / 69.1% | 338 to 364 (172) |
| Plumber, sealed 1 ([report](eval/reports/sealed-run.md)) | 164 | 15 of 15 | 73.1% | 74.0% | 78.1% / 89.6% | 161 to 171 (157) |
| Plumber, sealed 2 ([report](eval/reports/sealed-v2-run.md)) | 136 | 16 of 16 | 75.8% | 83.6% | 80.2% / 96.5% | **66 to 81 (188)** |
| Electrician, first set ([report](eval/reports/fernhollow-run.md)) | 83 | **11 or 12 of 13** | 70.7% | 67.1% | 72.9% / 74.6% | 390 to 511 (183) |
| Electrician, sealed 1 ([report](eval/reports/fernhollow-sealed-run.md)) | 113 | **23 of 29** | 59.5% | 78.8% | 79.1% / 87.6% | 519 to 536 (181) |
| Electrician, sealed 2 ([report](eval/reports/fernhollow-sealed-v2-run.md)) | 129 | **35 of 36** | 66.7% | 80.9% | 80.0% / 93.9% | 152 to 188 (171) |

Rates are means over the three passes; a fixed seed moves few items between passes. Cost weights each route error by assumed minutes of a person's time (a missed safety message 100, a missed escalation 20, an extra one 4; [D-094](docs/DECISIONS.md)) and compares it with sending every message to a person.

What the table shows:
- **Safety.** No plumbing safety message was missed on any unseen set (43 of 43). The electrician's emergency terms missed messages twice and were widened twice ([D-106](docs/DECISIONS.md), [D-110](docs/DECISIONS.md)); on the newest set, written by a blind session after the second widening, 35 of 36 were escalated and the widened terms alone caught 3 or 4 of them per pass without new false alarms ([D-113](docs/DECISIONS.md)).
- **Understanding missed its target on every unseen set** (59.5% to 75.8% against 85%). A second labeller agreed with the intent labels on only 73% of a sample ([D-089](docs/DECISIONS.md)), so part of the gap is doubt about the labels. A word-count classifier with no model scored 51% to 59% on the same kind of messages ([D-093](docs/DECISIONS.md)).
- **Routing beat sending everything to a person on one set only**, the plumber's second sealed set, and was about even on the newest electrician set. Spam is rarely archived (1 of 7 and 1 of 9 on the plumber's sealed sets), and 5 to 24 messages per set were escalated that need not be.
- **Drafts:** the figure check found one figure not in the sources, on the first sealed set, and blocked that draft; on the other sets it found none. No judge scores whether a draft is good (see below).

**The person who approves is the last check, and a trial showed it is weak** ([report](eval/reports/review-trial.md), [D-066](docs/DECISIONS.md)). One reviewer, who also built the system, checked 24 drafts in a median of 37 seconds each but approved all five drafts with a planted real problem (exact 95% interval 0 to 52% caught). The review screen now points at those kinds of problem ([D-077](docs/DECISIONS.md)), but that has not been tried on a reviewer.

On the **tuned** messages, which the system was adjusted on, intent was 83.5% and route 78.0%; those are not results. Thinking mode is on: it scored higher on four of five measures, though no difference was large enough to call real ([D-063](docs/DECISIONS.md)). Each unseen set is guarded by a committed ledger and hash so it cannot be quietly rerun ([D-061](docs/DECISIONS.md), [D-078](docs/DECISIONS.md)).

## What the numbers do not say

- **Invented data, one labeller.** The documents, prompts, labels and test messages were all written by the same author (an AI model): the held-out set is unseen but not blind. Results on an invented business show the machinery works; they do not show how it behaves on a real business's messy inbox. A second person labelled a blind sample of 60 items and agreed with the existing primary-intent labels on 44 (73.3%, Cohen's kappa 0.70; D-089). The 85% intent target is therefore hard to reach under the current labelling rules, and some of the gap in the table is probably doubt about the labels, not only model error. The sample is small (interval about 61% to 83%), so how much is not known. The largest group of differences was booking versus availability, now written into the rules (D-090).
- **Every unseen set in the table is spent.** Each sealed set was written by a separate session, kept out of the repository, sealed by a committed hash, and run once by one fixed system with the number of passes declared first (D-071, D-078, D-104, D-111). Fixes made after a run, and measured on the set that showed the problem, are development figures until a fresh set judges them. One more plumbing set (`kestrel-3`, D-112) is sealed and not yet run.
- **Small counts.** Twelve safety items with no misses are compatible with a true miss rate near one in four; 35 of 36, with one up to about one in seven. Each escalation reason has a handful of items per set. The overall rates depend on the mix, which is built to exercise every rule and is not a real inbox.
- **No score of draft quality.** A judge from a sibling project can ask whether each claim is backed by the passages (D-079). On 36 drafts labelled by hand it agreed with the labeller on 18 and flagged 16 drafts the labeller called fine; run only on the sentences that make claims it agreed on 29 of 36 (Cohen's kappa 0.07, from 2 drafts the labeller flagged), and with that rule it flags about one good draft in seven (D-082). It notices an invented perk, policy, credit or promise and notices a sentence about how the desk works in 7 of 15 cases. The labeller built the system and the sheet's rule, and the claims-only rule was changed once after seeing which labelled drafts it missed, so these are development figures and the judge is a screen, not a score.
- **A fixed seed** gives little run-to-run spread (on the sealed set 7 of 164 items moved intent between the three passes), which may not hold on another machine.

## Where it goes wrong

What follows is what the tests and the measured runs show, with the file that shows it.

**The person who reviews did not catch what the checks missed.** See the trial above. Do not read "a person approves everything" as a safety guarantee: it is only as good as the review, and the review screen did not point at the things the checks cannot see. Since the trial it does (D-077, see "What to improve"), but that has not been tried on a reviewer.

**Prompt injection is only partly stopped.** There are three lines of defence: screening patterns (plain code), the draft checks (plain code), and a person who reads every draft (see the trial). Nothing is sent automatically.
- Screening flagged all 6 injection items in the tuned set, which its patterns were written with in view. On the held-out set it flagged 1 of 4; the other 3 reached a reviewer as ordinary replies.
- Five invented messages in new words (a role-play as the owner, a fake notice, a request to paste the model's guidelines, a quoted forward, a request to add a sentence) were not flagged by screening; since D-074 the role-play is, and the other four are not ([tests/test_injection_end_to_end.py](tests/test_injection_end_to_end.py)). Run once each through the real model, three were not obeyed, one was obeyed and blocked by the commitment check, and one ("end your reply with the sentence ...") was obeyed and reached the reviewer as a ready draft. Five messages and one run each is a check, not a rate.
- Since the held-out run (D-074, D-075), screening patterns were widened and the model is also asked whether a message is aimed at the assistant. On a development set written by the author of the prompts, the patterns alone flagged 1 of 12 injections in wording written after them and the model question 10 of 12, with 1 false alarm in 46 ordinary messages overall. Those are development numbers. On the sealed run (D-087) the injection category had 15 items: screening caught 7, 8 were not caught and 4 of those reached a reviewer as ordinary replies; 1 of 15 near misses was flagged wrongly.
- The draft checks compare phrases and values. Since D-091 a red-team set of invented sentences ([tests/test_checks_redteam.py](tests/test_checks_redteam.py)) holds wordings the checks must stop, wordings they must allow, and known misses: "I'll make sure a courtesy credit is applied" and an invented perk with no figure in it still pass every check. The checks were changed with that set in view, so it is a development set, not a rate.

**Routing usually costs more than sending everything to a person** ([D-094](docs/DECISIONS.md), [D-109](docs/DECISIONS.md); the cost column in the table). Under the assumed costs it was cheaper only on the plumber's second sealed set, where the two break even when a missed escalation costs about 68 to 103 minutes. Where it lost, missed escalations (and, for the electrician, missed safety messages) cost more than the time saved on drafts. The costs are assumptions; each report gives the counts so other costs can be applied.

**Understanding is weaker on unseen messages.** On the held-out set primary-intent accuracy was 69.8% against a target of 85%, and policy-exception requests were escalated 1 time in 6. All 3 spam items in the first pass were escalated and none was archived. Since then (D-074) a separate yes/no question about exception requests was added: it flagged 19 of 20 requests on a development set and all 8 on the tuned set, whose wording the prompts were written with in view. It adds one model call per message (median model time 7.9 s on the tuned set). The held-out figures above are unchanged because the held-out set is spent; the sealed run (D-087) is the result for the final system. Later fixes (D-085) addressed the other held-out groups with mixed results: a definition of opening hours moved hours questions read correctly from 9 to 16 of 17 on a development set; a longer spam definition did not help (5 to 6 of 12) and was dropped; relative dates such as "today" are now dropped in code because the model ignored the prompt rule; and an imagined burst pipe no longer trips the safety-keyword net (gas, carbon monoxide and electrical terms always do). On the tuned split primary-intent accuracy stayed near 83% (102 of 123), and the sealed run then measured 73.1%. Politely worded spam still goes to a reviewer, because archiving needs a code score of 0.8 as well as the model's reading and archiving a real customer's message is the costly error.

**Draft style.** About one draft in five (one in three of the model-written ones) fails the non-blocking structure check (no greeting or sign-off), and some arrive with their paragraph breaks collapsed. The business documents spell "neighbourhood" the British way, and drafts copy it. Since then (D-076) the greeting, sign-off and paragraph breaks are set in code: on 60 tuned items 32 of 32 drafts passed that check, which is largely by construction and says nothing about content.

**Draft content that no check catches.** Reading drafts found four patterns, each now handled by a prompt rule or a warning on the review screen, none by a blocking check: a sentence of sympathy the message does not call for (D-080, prompt rule and a tone mark); a request for a detail the customer already gave (D-081, the writer is told what is known and a sentence that asks for it is marked); a sentence that uses a passage's words and gets its meaning wrong ("sales tax on all parts and labour" where labour is not taxed), which no mark finds; and a reply that defers a price the passages list (D-083, a mark when the message asks the cost, a priced line fits what was asked and the draft names no price). The prompt rules were tried on replays of the tuned drafts with the real model, the same items they were written from; a full tuned pipeline run after them (D-084) showed no regression: `STRUCTURE` and the other checks passed on 86 or 87 of 87 drafts, route accuracy rose from 75.6% to 82.2% and `POLICY_EXCEPTION_REQUEST` recall from 3 of 8 to 8 of 8, on the split the prompts were written against. In that run 19% of reply sentences carried the "not from your documents" mark, mostly generic offers, and three of them were correct prices worded differently from the pricing line. The marks are warnings for a person who reads the reply and are not tested on a reviewer.

**Failures are handled, and each leaves the inquiry where a person can find it** ([tests/test_failure_paths.py](tests/test_failure_paths.py)). If the model is offline or gives invalid JSON twice, the inquiry becomes `failed` at its stage and Retry resumes there. If the knowledge base is offline, it fails at retrieval and nothing is drafted without sources. If the database is locked, a write is refused with a generic 500 and a request id, nothing is half stored, reads still work, and the background worker carries on once the lock clears. An inquiry that was accepted is never lost.

**Single user, one machine.** There is no authentication, and the server listens on `127.0.0.1` only. It answers only requests addressed to this machine's own names, and takes changes only from pages on this machine or from tools that send no `Origin`, so another website open in the same browser can neither read the queue through DNS rebinding nor post a form to it (D-092). Any program running on the machine can still call it. The size limit (413) and the rate limit (429, 300 requests a minute for new inquiries and imports) are checked inside the one process, for all callers together, and the rate counter starts again when the server restarts.

**Deleting data.** An inquiry can be deleted from its page (it asks first; it cannot be undone): the message, drafts, reviews and history go, and one audit event with the id and no text is kept. Closed inquiries can be removed by age with `python -m citedesk.db purge --older-than DAYS` (`--dry-run` lists them first). Deleted text is overwritten in the database file; backups and other copies are not touched (D-101).

**Logs hold ids, codes and type names, not text.** The server writes no access log (its lines would carry search text), and an unexpected error is answered by the app so the server never logs a traceback ([tests/test_hardening_logs.py](tests/test_hardening_logs.py)). Dependencies were audited with `pip-audit` and `npm audit`: nothing was reported on 2026-10-29. On 2026-11-03 `pip-audit` was still clean and `npm audit` reported one moderate advisory (`minimatch`, in the lint tooling only; none for production dependencies; the only offered fix is a breaking change to the lint plugins, so it was not applied). The advisory was later dismissed on GitHub because the affected code path is not used by the lint tooling (D-096). These are point-in-time results.

## What this could save

**This is an illustration with every assumption labelled. No saving was measured.**

| Quantity | Value | Where it comes from |
|---|---|---|
| Time to check a ready draft | about 37 s (p90 81 s) | **Measured**, one reviewer on 20 invented drafts ([report](eval/reports/review-trial.md)) |
| Share of inquiries that reach a ready draft | 43 of 76 in the first held-out pass | **Measured** on an invented mix ([report](eval/reports/heldout-think-on.md)); a real inbox will differ |
| Minutes to write a reply by hand | 5 | **ASSUMPTION**: nobody timed hand-written replies |
| Inquiries per day | 20 | **ASSUMPTION** |
| Time to handle an escalated inquiry | the same as by hand | **ASSUMPTION**: the tool saves nothing on these |

On those assumptions, a day of 20 inquiries would take about 100 minutes by hand. With the tool, about 11 ready drafts at about 1 minute each and 9 handled by hand at 5 minutes comes to about 56 minutes: roughly 45 minutes saved, **if** a review takes about a minute and the reviewer catches problems, which the trial does not show. Change any assumption and the answer changes. The Insights screen holds your own number for the hand-written time and labels the result "Estimate based on your assumption".

## Run it

**Tested on Windows 11 with PowerShell.** CI runs the tests on Linux. Running the whole stack on macOS or Linux is untested. You need Python 3.13, Node.js 22 and npm, [Ollama](https://ollama.com) with `qwen3:8b`, and [rag-project](https://github.com/Nbhaskell/rag-project) (a separate project, the knowledge base) with the `embeddinggemma` embedding model.

```powershell
git clone https://github.com/Nbhaskell/citedesk.git
cd citedesk
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
Copy-Item .env.example .env
```

**The tests need no model, network or GPU:**

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
```

**The web app's checks** (from `web\`, once `npm ci`): `npm run lint; npm run typecheck; npm test; npm run build`.

**The demo, in one command.** Start Ollama (with `qwen3:8b` and `embeddinggemma` pulled), install the web app once (`cd web; npm ci`), and have [rag-project](https://github.com/Nbhaskell/rag-project) set up in a folder next to this one (or pass `--rag-project <folder>`). Then:

```powershell
.\.venv\Scripts\python.exe -m tools.start
```

It checks Ollama, starts rag-project on the invented plumber's documents (indexing them the first time) or reuses one that already serves them, then starts the API and the web app, and stops what it started on Ctrl+C. `--business fernhollow` runs the invented electrician instead (D-098, D-102). Starting each part by hand is described in [docs/knowledge-base-contract.md](docs/knowledge-base-contract.md).

In a second terminal, load a few invented inquiries:

```powershell
.\.venv\Scripts\python.exe -m tools.import_inquiries --limit 8
```

Open <http://127.0.0.1:5174>. The API is at <http://127.0.0.1:8100/api/status>. Each inquiry takes 25 to 45 seconds to read, retrieve, draft and check on the development machine.

**Reproduce the evaluation** (needs Ollama and rag-project running and indexed, about 40 minutes per pass; runs are saved under `eval\runs\`, which is git-ignored). The runner asks the system, the scorer reads a saved run with no model, and the comparison tests two settings over repeat passes:

```powershell
.\.venv\Scripts\python.exe -m tools.eval_run --passes 3 --label think-on
.\.venv\Scripts\python.exe -m tools.eval_score eval\runs\<run>.run.json
.\.venv\Scripts\python.exe -m tools.eval_run --passes 3 --thinking off --label think-off
.\.venv\Scripts\python.exe -m tools.eval_compare --a <off runs> --b <on runs> --label-a think-off --label-b think-on
```

The held-out split has been run once and the runner refuses it again without a written justification (the ledger is [eval/heldout_ledger.json](eval/heldout_ledger.json)); do not use it to tune.

## What to improve

Open items, in priority order:

1. **Try the review aids on a reviewer.** The review screen now shows, beside the draft, the line each figure comes from, the greeting name next to the sender, and the sentences no passage backs (D-077), plus sympathy the message does not call for (D-080), requests for details already given (D-081) and a listed price the reply leaves out (D-083). Against the six drafts of the first trial the sentence marks and the name warning point at all five real problems, and about one ordinary sentence in ten is marked; those are development numbers from code written with the problem kinds in view. Whether a person catches more with them is not known: it needs a rerun of the reviewer trial with new plants in new wording on different items, and ideally a second reviewer.
2. **A set written by a person.** Every test message so far was written by the same AI model family that wrote the system. Thirty to fifty messages written by someone who knows a trade business would test wording no model suggested, above all for safety.
3. **Understanding accuracy** (59.5% to 75.8% against 85% on the unseen sets): spam that is escalated instead of archived, injection wordings that get through screening, and items escalated that need not be. Any change needs a fresh sealed set to be claimed; one (`kestrel-3`) is ready. A second labeller agreed with the existing intent labels on 73.3% of a 60-item sample (D-089), so label doubt is probably part of the gap (how much is not known); the booking versus availability rule is now written (D-090), and any further rule changes come before more prompt work.
4. **The phrase-list checks** (commitments, injection echo): they miss paraphrases. D-091 closed the gaps found by a review (a negation from another clause, a source phrase used only to deny it, spelled-out money, bare domains) and keeps the remaining known misses in a red-team test. Wordings written by someone who has not seen the checks would give the first real catch rate.
5. **Spelling in the business documents:** they spell "neighbourhood" the British way and drafts copy it (regenerate the documents from `facts.json`, then re-index and re-run the tuned evaluation). Greetings, sign-offs and paragraph breaks are set in code since D-076.
6. **A second labeller** for the judge's 36 hand labels and a score of draft quality that does not rest on the writer of the system (D-079, D-082). Since D-095 the Insights screen shows draft quality from use (how much reviewers edit, how often they reject, and whether drafts with a warning are changed more often); it has not yet seen real reviews. Under-answering is covered for prices only (D-083); other kinds, such as hours and policies, are not.
7. **Later:** a hosted model behind the same interface (message text would leave the machine), Gmail draft creation (drafts only, never send), and a real pilot with a willing business, which needs consent, anonymisation and its own evaluation.

## Licence

MIT. See [LICENSE](LICENSE). The invented data in `universe/` and `eval/golden/` is released under the same licence. The web app's build bundles two fonts from `@fontsource`, Atkinson Hyperlegible and Source Serif 4, under the SIL Open Font License 1.1; neither font file is stored in this repository. Dependencies keep their own licences (the runtime Python ones are MIT, BSD, Apache-2.0 and PSF-2.0; the JavaScript ones are mostly MIT, with a few MPL-2.0, OFL-1.1 and CC-BY-4.0 packages used only for building, testing or as bundled fonts and data).

## Documentation

[docs/](docs/): [PRD](docs/PRD.md) (what and why), [TRD](docs/TRD.md) (architecture, stages, checks, API), [APP_FLOW](docs/APP_FLOW.md), [UI_UX_DESIGN_BRIEF](docs/UI_UX_DESIGN_BRIEF.md), [UI_DESIGN_PLAN](docs/UI_DESIGN_PLAN.md), [BACKEND_SCHEMA](docs/BACKEND_SCHEMA.md), [RULES](docs/RULES.md) (the rules that do not bend), [IMPLEMENTATION_PLAN](docs/IMPLEMENTATION_PLAN.md), [DECISIONS](docs/DECISIONS.md) (every decision not covered by the others, D-001 to D-113), [REVIEW_TRIAL](docs/REVIEW_TRIAL.md), and [the knowledge-base contract](docs/knowledge-base-contract.md).
