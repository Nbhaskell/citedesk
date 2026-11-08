# Cost-weighted route score

> SYNTHETIC DATA. Ids, routes and counts only; no message text.

Split: **tuned** (135 items). Costs are ASSUMPTIONS in rough minutes of a person's time, fixed before scoring (D-094): missed safety 100, real message archived 50, missed escalation 20, extra escalation 4, spam kept 1, wrong kind of reply 1. Lower is better.

| System | Cost per 100 | Missed safety | Lost | Missed escalation | Extra escalation | Spam kept | Wrong reply kind | Right |
|---|---|---|---|---|---|---|---|---|
| eval-tuned-think-on-20261029-181814-p1 | 182 | 0 | 0 | 9 | 15 | 0 | 6 | 105 of 135 |
| eval-tuned-think-on-20261029-185612-p2 | 153 | 0 | 0 | 7 | 15 | 0 | 6 | 107 of 135 |
| eval-tuned-think-on-20261029-193926-p3 | 185 | 0 | 0 | 9 | 16 | 0 | 6 | 104 of 135 |
| pipeline-v1-tuned-20261106-225350 | 103 | 0 | 0 | 4 | 13 | 0 | 7 | 111 of 135 |
| Escalate everything (no model) | 247 | 0 | 0 | 0 | 82 | 6 | 0 | 47 of 135 |
| Draft everything (no model) | 1192 | 8 | 0 | 39 | 0 | 6 | 23 | 59 of 135 |

## Break-even with escalating everything

- `eval-tuned-think-on-20261029-181814-p1`: the two cost the same when one missed escalation costs 29.8 (the assumed cost is 20); above that, escalating everything is cheaper
- `eval-tuned-think-on-20261029-185612-p2`: the two cost the same when one missed escalation costs 38.3 (the assumed cost is 20); above that, escalating everything is cheaper
- `eval-tuned-think-on-20261029-193926-p3`: the two cost the same when one missed escalation costs 29.3 (the assumed cost is 20); above that, escalating everything is cheaper
- `pipeline-v1-tuned-20261106-225350`: the two cost the same when one missed escalation costs 68.8 (the assumed cost is 20); above that, escalating everything is cheaper

## Costly errors in `eval-tuned-think-on-20261029-181814-p1`

- missed_escalation: exception-cash-no-invoice, exception-extend-warranty, exception-price-match, exception-skip-written-estimate, exception-waive-travel-fee, followup-any-update-on-quote, followup-is-friday-still-on, unanswerable-free-remodel-estimate, unanswerable-gas-water-heater-swap

## Costly errors in `eval-tuned-think-on-20261029-185612-p2`

- missed_escalation: exception-price-match, exception-skip-written-estimate, exception-waive-travel-fee, followup-any-update-on-quote, followup-is-friday-still-on, unanswerable-free-remodel-estimate, unanswerable-gas-water-heater-swap

## Costly errors in `eval-tuned-think-on-20261029-193926-p3`

- missed_escalation: exception-cash-no-invoice, exception-extend-warranty, exception-price-match, exception-skip-written-estimate, exception-waive-travel-fee, followup-any-update-on-quote, followup-is-friday-still-on, unanswerable-free-remodel-estimate, unanswerable-gas-water-heater-swap

## Costly errors in `pipeline-v1-tuned-20261106-225350`

- missed_escalation: followup-any-update-on-quote, followup-is-friday-still-on, unanswerable-free-remodel-estimate, unanswerable-gas-water-heater-swap

## What this cannot tell you

- The costs are assumptions. The counts per kind are given so other costs can be applied.
- The mix of the evaluation sets is not a real inbox: they hold more messages that should escalate than a business would see, which favours escalating everything.
- An escalated message is assumed to be handled well by a person, and a draft that should not exist is costed once, not by what happens if it is approved.
