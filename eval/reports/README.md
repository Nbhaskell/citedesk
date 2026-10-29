# Evaluation reports

> SYNTHETIC DATA. Every customer and message here is invented. These files hold ids, codes and
> numbers only, never message or draft text.

## What is here

| File | What it is |
|---|---|
| `tuned-think-off.md` / `.json` | Three passes of the system with `ENABLE_THINKING` off, scored one by one, then the run-to-run spread |
| `tuned-think-on.md` / `.json` | The same with `ENABLE_THINKING` on |
| `tuned-thinking-comparison.md` / `.json` | Off against on: difference, pass interval, paired bootstrap, and a call per measure |

Produced by `tools.eval_run`, `tools.eval_score` and `tools.eval_compare` (D-062) from six saved
runs on 2026-10-29: code at commit `2d959c4`, model `qwen3:8b`, `understand-v1` and `draft-v1`
prompts, rag-project with 83 chunks, the **tuned** split (135 items). Raw run files stay in
`eval/runs/` (git-ignored: they hold the invented messages and drafts).

## Held-out: not run yet

No system has been run on the held-out split. `eval/heldout_ledger.json` is empty. The numbers
above are tuned numbers: the system was adjusted while looking at these items, so they flatter it.
The held-out result, run once by one fixed system (D-061), will be reported separately.

## Tuned results (means over three passes)

| Measure | Thinking off | Thinking on | Call |
|---|---|---|---|
| Primary-intent accuracy (target 85%) | 77.2% | 83.5% | unclear |
| Route accuracy, whole pipeline | 74.3% | 78.0% | unclear |
| Escalation precision | 70.5% | 71.6% | unclear |
| Escalation recall | 78.0% | 82.3% | unclear |
| HEALTH_SAFETY recall (n = 8; target: no misses) | 8/8 | 8/8 | met in all six passes |

- **Thinking on and off cannot be told apart on these items.** Thinking on was higher on every
  measure, but no difference beat both the run-to-run spread and the paired bootstrap, so each is
  "unclear", which is not "no effect". The test could not have seen differences under about 5 to
  9 percentage points.
- **Cost of thinking** (first pass of each setting): the understand step's median went from 2.2 s
  to 5.4 s and the whole item's median from 12.9 s to 14.6 s. Retrieval and drafting times also
  differ between the runs although the setting does not touch them, so treat timings as rough.
- **Known gaps, deliberately not fixed:** recall for `POLICY_EXCEPTION_REQUEST` and
  `REFUND_OR_DISPUTE`, the draft problems of D-049, and `ADDRESSES_ASK` (no judge reads the
  drafts). In the first thinking-off pass the routes were wrong on all 4 partnership items and all
  6 policy-exception items.

## What this cannot tell you

- One labeller wrote every label, and the same author wrote the documents, the prompts and the
  labels: the set is unseen but not blind.
- 135 items built to exercise every rule. Rates say nothing about a real inbox. Counts per
  escalation reason are small.
- The runs use a fixed seed at temperature 0, so spread between passes may be smaller here than on
  another machine.
- The checks compare values and phrases, not meaning. No judge has read the drafts.
