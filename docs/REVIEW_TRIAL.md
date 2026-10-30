# Reviewer trial (protocol, written before the trial)

Status: run on 2026-10-30, one reviewer, one sitting. Results: `eval/reports/review-trial.md` and
`.json`; decision record D-066. Deviation from the protocol: the reviewer used "Redraft with guidance"
on three inquiries, which calls the real model; the scorer uses the first decision on each inquiry
and its timing, and ignores later ones.

All messages, drafts and customers are invented. The trial uses the real review screen on the
tuned inbox, locally, and nothing is sent anywhere.

## Why

Every evaluation so far (D-044, D-049, D-064) scores the AI pipeline. The product's safety argument
rests on a person reading each draft ("nothing is ever sent automatically"), and its value claim is
that a ready draft can be checked in about a minute. Neither has been measured. PRD section 7 lists
"reviewer time per inquiry" as a success metric measured in a small timed trial; this is that trial,
with a second question added: do drafts that pass every automated check but are still wrong get
caught by the person?

## Questions and what would count as an answer

| Question | Measure | Reported as |
|---|---|---|
| How long does a review take? | The app's own `review_seconds` (from opening the review panel to the decision), per inquiry | Median, p90 and the range, with n; ordinary drafts and drafts with a problem apart |
| Are ordinary drafts handled well? | Of the ordinary drafts, how many were approved unchanged, edited, rejected or escalated | Counts |
| Does a person catch a wrong draft that the checks passed? | Of the drafts with a planted problem, how many were not approved as they stood (edited to fix, rejected or escalated) | Counts out of 6, with the problem types named only after the sitting |
| Is review faster than writing the reply? (optional) | Time to write 5 of the replies from the business documents without a draft | Median per reply, labelled as a small unaided sample |

There is no pass mark. The numbers are reported as they come out, with the limits below.

## Material

- **24 inquiries**: 4 for a warm-up that is not scored, then 20. Chosen from the tuned set, the kinds
  an owner would see in a day (prices, hours, bookings, a missing detail, an out-of-scope request).
  Items that must be escalated by rule (safety, complaints, legal) are left out: those never reach
  a "ready" draft.
- **14 ordinary drafts**, written by the real pipeline (`qwen3:8b`, rag-project) and passed by all
  checks. Nothing in them is altered.
- **6 drafts with one planted problem each.** Each starts as a real pipeline draft and has one
  change made by a script. The changed draft is run through the real checks, and a plant is used only
  if **every blocking check still passes**, so it appears as an ordinary ready draft. The problem
  types are decided by the person who prepares the trial and kept in `eval/trial/plants.json`
  (git-ignored until the sitting is over), so the reviewer does not read them in advance. They are
  kinds of mistake the checks are known not to see (see the README's known weaknesses), written in
  wording not used in earlier tests.
- Order is shuffled with a recorded seed. The reviewer is told that some drafts contain a problem,
  and not how many or what kind.

## Sitting

- One sitting of about an hour, uninterrupted, on the real queue (API and web app running, drafts
  already made, so no model is needed while reviewing).
- Instruction to the reviewer: *"Review each one as if it were going to the customer. Approve it,
  edit it, reject it or escalate it. Take the time you would really take."*
- The warm-up items come first and are not counted.
- If the reviewer stops for a break or is interrupted in the middle of an item, that item's time is
  marked and left out of the timing figures (the app's timer keeps running).
- Optional, afterwards: write 5 replies from the documents without drafts, timed by stopwatch.

## Running the sitting

The queue is already prepared (`data\trial.db`, 24 inquiries, all waiting for review, in the sitting
order). No model or knowledge base is needed to review. From the repo root, in PowerShell:

```powershell
Copy-Item data\trial.db data\trial.pristine.db     # a spare copy, in case the sitting must restart
$env:CITEDESK_DB_PATH = "data\trial.db"
.\.venv\Scripts\python.exe -m citedesk             # API on 127.0.0.1:8100; leave it running
```

In a second terminal: `cd web; npm run dev`, then open <http://127.0.0.1:5174>.

- Work the queue from the top, in order, without skipping. The first 4 are the warm-up.
- Do not open `eval\trial\`, `tools\trial_plants.py`, `tools\trial_prepare.py` or
  `tests\test_trial.py` until you have finished: they say what is planted.
- Do not use the Insights screen or re-open a decided inquiry during the sitting.
- If you are interrupted partway through an inquiry, finish it as usual and note its id; it is left
  out of the timing with `--exclude`.
- To start again, stop the API, copy `data\trial.pristine.db` over `data\trial.db`, and begin from
  the top. Only the final attempt is scored.

## Scoring (code, after the sitting)

```powershell
.\.venv\Scripts\python.exe -m tools.trial_score --db data\trial.db `
  --md eval\reports\review-trial.md --json eval\reports\review-trial.json
# optional: --exclude <ids interrupted> --unaided <seconds for each hand-written reply>
```

`tools/trial_score.py` reads the decisions and `review_seconds` from the database and `plants.json`,
and writes ids, decisions and numbers only: no message or draft text. It prints counts, medians and
the range, and the exact binomial 95% interval for the catch count (6 planted drafts give a wide
interval; the report says so in words).

## What this cannot tell you (written in advance)

- **One reviewer who also built the system.** They know the screens and what the checks do, so their
  times and catch rate flatter the system. A second reviewer who has not seen the project would be
  much stronger.
- **The reviewer already knows some examples** (a made-up perk, a promise worded outside the phrase
  list). The plants use other wording, but the reviewer is not naive to the kinds.
- **A high share of bad drafts** (6 of 20) makes people more careful than they would be when
  problems are rare. The catch rate is probably an upper bound.
- **Six planted drafts** cannot give a rate. Counts only.
- **Invented messages and an invented business.** This shows how the screens work for one person,
  not how a real front desk would cope.
- It does not measure whether the model reads messages correctly. That is the intent-accuracy
  result (D-064) and this trial does not change it.

## Outputs

`eval/reports/review-trial.md` and `.json` (ids, decisions, timings, counts), a short decision
record in `docs/DECISIONS.md`, and a line in the README's known weaknesses and "what this could save"
sections. If the reviewer misses a planted problem, the follow-up is a separate decision (for
example, marking claims no source supports), not a change made in this trial.
