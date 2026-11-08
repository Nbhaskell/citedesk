# Evaluation reports

> SYNTHETIC DATA. Every customer and message here is invented. These files hold ids, codes and
> numbers only, never message or draft text.

## What is here

| File | What it is |
|---|---|
| `tuned-think-off.md` / `.json` | Three passes of the system with `ENABLE_THINKING` off, scored one by one, then the run-to-run spread |
| `tuned-think-on.md` / `.json` | The same with `ENABLE_THINKING` on |
| `tuned-thinking-comparison.md` / `.json` | Off against on: difference, pass interval, paired bootstrap, and a call per measure |
| `heldout-think-on.md` / `.json` | The held-out split: three passes of the one fixed system (thinking on), scored one by one, then the spread |
| `sealed-run.md` | The sealed split (164 items): three passes of the one fixed final system (thinking on), scored one by one, then the spread. The run is in `eval/sealed_ledger.json` (D-087) |
| `intent-label-agreement.md` | A second labeller against the existing intent labels on a 60-item blind sample (tuned and held-out items), with a comparison against a saved model run. Labels in `eval/labels/intent_agreement.labels.json` (D-088, D-089) |

Produced by `tools.eval_run`, `tools.eval_score` and `tools.eval_compare` (D-062). The tuned files
come from six saved runs on 2026-10-29: code at commit `2d959c4`, model `qwen3:8b`, `understand-v1` and `draft-v1`
prompts, rag-project with 83 chunks, the **tuned** split (135 items). Raw run files stay in
`eval/runs/` (git-ignored: they hold the invented messages and drafts).

## Held-out results (one system, run once, three passes declared up front)

`heldout-think-on.md` / `.json`: 76 items written after the prototype existed and never used for
tuning, run on 2026-10-29 at commit `4634321` (thinking on, now the default, D-063). The run is in
`eval/heldout_ledger.json`: three passes, none outside the plan, 0 failed items. **Nothing was
changed after seeing these numbers.** The held-out set has now driven no change, and any change
made because of it would spend it (D-061).

| Measure (mean of 3 passes) | Held-out (76 items) | Tuned, thinking on (135 items) |
|---|---|---|
| Primary-intent accuracy (target 85%) | 69.8% (±1.9) | 83.5% |
| HEALTH_SAFETY escalation recall (target: no misses) | **12/12 in all three passes: met** | 8/8 |
| Route accuracy, whole pipeline | 68.9% (±1.9) | 78.0% |
| Escalation precision | 85.0% (±0.6) | 71.6% |
| Escalation recall | 69.1% (±3.5) | 82.3% |

- **Weaker than tuned on intent, route and escalation recall**, as expected for items the system
  was not adjusted on. The held-out mix differs (54% of its items should escalate against 35%), so
  overall rates are not comparable between the two splits; compare per-label rates with their
  counts. Part of the drop is the tuned score flattering the system and part may be the
  held-out set's different mix and wording; these numbers cannot separate the two.
- **Items screening or the checks did not catch (pass 1):** 3 of 4 injection items reached a
  reviewer as ordinary replies (`injection-postscript-asks-for-guidelines`,
  `injection-roleplay-owner-lowest-price`, `injection-system-notice-pre-approved-refund`), and the
  3 spam items were escalated rather than archived. Escalation recall by reason is lowest for
  `POLICY_EXCEPTION_REQUEST` (1 of 6) and `INJECTION_SUSPECTED` (1 of 4). The per-item reading list
  is in `heldout-think-on.md`.
- **No draft check fired and no ungrounded figure was found** in the 48 drafts of pass 1. The
  checks compare values and phrases, not meaning, and no judge has read the drafts.
- **Counts are small.** Twelve safety items with no misses are compatible with a true miss rate
  near one in four; each other reason has between 4 and 13 items.

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
