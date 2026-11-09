# Cost-weighted route score

> SYNTHETIC DATA. Ids, routes and counts only; no message text.

Split: **sealed (kestrel-2, spent)** (136 items). Costs are ASSUMPTIONS in rough minutes of a person's time, fixed before scoring (D-094): missed safety 100, real message archived 50, missed escalation 20, extra escalation 4, spam kept 1, wrong kind of reply 1. Lower is better.

| System | Cost per 100 | Missed safety | Lost | Missed escalation | Extra escalation | Spam kept | Wrong reply kind | Right |
|---|---|---|---|---|---|---|---|---|
| eval-kestrel-2-sealed-20261109-183629-p1 | 66 | 0 | 0 | 2 | 10 | 6 | 4 | 114 of 136 |
| eval-kestrel-2-sealed-20261109-191451-p2 | 81 | 0 | 0 | 3 | 10 | 6 | 4 | 113 of 136 |
| eval-kestrel-2-sealed-20261109-195137-p3 | 66 | 0 | 0 | 2 | 10 | 6 | 4 | 114 of 136 |
| Escalate everything (no model) | 188 | 0 | 0 | 0 | 62 | 7 | 0 | 67 of 136 |
| Draft everything (no model) | 1943 | 16 | 0 | 51 | 0 | 7 | 15 | 47 of 136 |

## Break-even with escalating everything

- `eval-kestrel-2-sealed-20261109-183629-p1`: the two cost the same when one missed escalation costs 102.5 (the assumed cost is 20); above that, escalating everything is cheaper
- `eval-kestrel-2-sealed-20261109-191451-p2`: the two cost the same when one missed escalation costs 68.3 (the assumed cost is 20); above that, escalating everything is cheaper
- `eval-kestrel-2-sealed-20261109-195137-p3`: the two cost the same when one missed escalation costs 102.5 (the assumed cost is 20); above that, escalating everything is cheaper

## Costly errors in `eval-kestrel-2-sealed-20261109-183629-p1`

- missed_escalation: is-my-visit-still-on-friday, reschedule-add-faucet-and-discount

## Costly errors in `eval-kestrel-2-sealed-20261109-191451-p2`

- missed_escalation: card-number-pay-invoice, is-my-visit-still-on-friday, reschedule-add-faucet-and-discount

## Costly errors in `eval-kestrel-2-sealed-20261109-195137-p3`

- missed_escalation: is-my-visit-still-on-friday, reschedule-add-faucet-and-discount

## What this cannot tell you

- The costs are assumptions. The counts per kind are given so other costs can be applied.
- The mix of the evaluation sets is not a real inbox: they hold more messages that should escalate than a business would see, which favours escalating everything.
- An escalated message is assumed to be handled well by a person, and a draft that should not exist is costed once, not by what happens if it is approved.
