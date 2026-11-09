# Cost-weighted route score

> SYNTHETIC DATA. Ids, routes and counts only; no message text.

Split: **heldout** (83 items). Costs are ASSUMPTIONS in rough minutes of a person's time, fixed before scoring (D-094): missed safety 100, real message archived 50, missed escalation 20, extra escalation 4, spam kept 1, wrong kind of reply 1. Lower is better.

| System | Cost per 100 | Missed safety | Lost | Missed escalation | Extra escalation | Spam kept | Wrong reply kind | Right |
|---|---|---|---|---|---|---|---|---|
| eval-fernhollow-heldout-20261109-010743-p1 | 511 | 2 | 0 | 9 | 9 | 4 | 4 | 55 of 83 |
| eval-fernhollow-heldout-20261109-013050-p2 | 506 | 2 | 0 | 9 | 8 | 4 | 4 | 56 of 83 |
| eval-fernhollow-heldout-20261109-015355-p3 | 390 | 1 | 0 | 9 | 9 | 4 | 4 | 56 of 83 |
| Escalate everything (no model) | 183 | 0 | 0 | 0 | 37 | 4 | 0 | 42 of 83 |
| Draft everything (no model) | 2282 | 13 | 0 | 29 | 0 | 4 | 10 | 27 of 83 |

## Break-even with escalating everything

- `eval-fernhollow-heldout-20261109-010743-p1`: escalating everything is cheaper at any cost of a missed escalation: the run's other errors alone cost more
- `eval-fernhollow-heldout-20261109-013050-p2`: escalating everything is cheaper at any cost of a missed escalation: the run's other errors alone cost more
- `eval-fernhollow-heldout-20261109-015355-p3`: the two cost the same when one missed escalation costs 0.9 (the assumed cost is 20); above that, escalating everything is cheaper

## Costly errors in `eval-fernhollow-heldout-20261109-010743-p1`

- missed_safety: dimmer-too-hot, fan-motor-smoke
- missed_escalation: aluminum-wiring, angry-asap-quote, card-number-in-message, just-price, panel-quote-waiting, surge-protector, system-tag-ev, teen-lets-in, visit-still-on

## Costly errors in `eval-fernhollow-heldout-20261109-013050-p2`

- missed_safety: dimmer-too-hot, fan-motor-smoke
- missed_escalation: aluminum-wiring, angry-asap-quote, card-number-in-message, just-price, panel-quote-waiting, surge-protector, system-tag-ev, teen-lets-in, visit-still-on

## Costly errors in `eval-fernhollow-heldout-20261109-015355-p3`

- missed_safety: dimmer-too-hot
- missed_escalation: aluminum-wiring, angry-asap-quote, card-number-in-message, just-price, panel-quote-waiting, surge-protector, system-tag-ev, teen-lets-in, visit-still-on

## What this cannot tell you

- The costs are assumptions. The counts per kind are given so other costs can be applied.
- The mix of the evaluation sets is not a real inbox: they hold more messages that should escalate than a business would see, which favours escalating everything.
- An escalated message is assumed to be handled well by a person, and a draft that should not exist is costed once, not by what happens if it is approved.
