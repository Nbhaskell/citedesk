# Cost-weighted route score

> SYNTHETIC DATA. Ids, routes and counts only; no message text.

Split: **sealed (fernhollow-3, spent)** (129 items). Costs are ASSUMPTIONS in rough minutes of a person's time, fixed before scoring (D-094): missed safety 100, real message archived 50, missed escalation 20, extra escalation 4, spam kept 1, wrong kind of reply 1. Lower is better.

| System | Cost per 100 | Missed safety | Lost | Missed escalation | Extra escalation | Spam kept | Wrong reply kind | Right |
|---|---|---|---|---|---|---|---|---|
| eval-fernhollow-3-sealed-20261109-211448-p1 | 188 | 1 | 0 | 4 | 14 | 4 | 3 | 103 of 129 |
| eval-fernhollow-3-sealed-20261109-214628-p2 | 152 | 1 | 0 | 2 | 12 | 4 | 4 | 106 of 129 |
| eval-fernhollow-3-sealed-20261109-221818-p3 | 183 | 1 | 0 | 4 | 12 | 4 | 4 | 104 of 129 |
| Escalate everything (no model) | 171 | 0 | 0 | 0 | 54 | 4 | 0 | 71 of 129 |
| Draft everything (no model) | 3345 | 36 | 0 | 35 | 0 | 4 | 11 | 43 of 129 |

## Break-even with escalating everything

- `eval-fernhollow-3-sealed-20261109-211448-p1`: the two cost the same when one missed escalation costs 14.2 (the assumed cost is 20); above that, escalating everything is cheaper
- `eval-fernhollow-3-sealed-20261109-214628-p2`: the two cost the same when one missed escalation costs 32.0 (the assumed cost is 20); above that, escalating everything is cheaper
- `eval-fernhollow-3-sealed-20261109-221818-p3`: the two cost the same when one missed escalation costs 16.0 (the assumed cost is 20); above that, escalating everything is cheaper

## Costly errors in `eval-fernhollow-3-sealed-20261109-211448-p1`

- missed_safety: shower-faucet-tingle
- missed_escalation: chase-panel-quote-monday, panel-brand, senior-discount-pensioner, visit-still-on-friday

## Costly errors in `eval-fernhollow-3-sealed-20261109-214628-p2`

- missed_safety: shower-faucet-tingle
- missed_escalation: senior-discount-pensioner, visit-still-on-friday

## Costly errors in `eval-fernhollow-3-sealed-20261109-221818-p3`

- missed_safety: shower-faucet-tingle
- missed_escalation: chase-panel-quote-monday, senior-discount-pensioner, visit-still-on-friday, whole-house-surge

## What this cannot tell you

- The costs are assumptions. The counts per kind are given so other costs can be applied.
- The mix of the evaluation sets is not a real inbox: they hold more messages that should escalate than a business would see, which favours escalating everything.
- An escalated message is assumed to be handled well by a person, and a draft that should not exist is costed once, not by what happens if it is approved.
