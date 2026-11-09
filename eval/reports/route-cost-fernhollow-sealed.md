# Cost-weighted route score

> SYNTHETIC DATA. Ids, routes and counts only; no message text.

Split: **sealed (fernhollow-2, spent)** (113 items). Costs are ASSUMPTIONS in rough minutes of a person's time, fixed before scoring (D-094): missed safety 100, real message archived 50, missed escalation 20, extra escalation 4, spam kept 1, wrong kind of reply 1. Lower is better.

| System | Cost per 100 | Missed safety | Lost | Missed escalation | Extra escalation | Spam kept | Wrong reply kind | Right |
|---|---|---|---|---|---|---|---|---|
| eval-fernhollow-2-sealed-20261109-162145-p1 | 519 | 5 | 0 | 2 | 10 | 4 | 2 | 90 of 113 |
| eval-fernhollow-2-sealed-20261109-165629-p2 | 536 | 5 | 0 | 3 | 10 | 4 | 2 | 89 of 113 |
| eval-fernhollow-2-sealed-20261109-173216-p3 | 526 | 5 | 0 | 2 | 12 | 4 | 2 | 88 of 113 |
| Escalate everything (no model) | 181 | 0 | 0 | 0 | 50 | 4 | 0 | 59 of 113 |
| Draft everything (no model) | 3111 | 29 | 0 | 30 | 0 | 4 | 11 | 39 of 113 |

## Break-even with escalating everything

- `eval-fernhollow-2-sealed-20261109-162145-p1`: escalating everything is cheaper at any cost of a missed escalation: the run's other errors alone cost more
- `eval-fernhollow-2-sealed-20261109-165629-p2`: escalating everything is cheaper at any cost of a missed escalation: the run's other errors alone cost more
- `eval-fernhollow-2-sealed-20261109-173216-p3`: escalating everything is cheaper at any cost of a missed escalation: the run's other errors alone cost more

## Costly errors in `eval-fernhollow-2-sealed-20261109-162145-p1`

- missed_safety: branch-pulled-service-wire, home-inspector-scorched-breaker, toddler-pried-off-cover, toilet-overflow-through-light, vacuum-blue-flash-last-sunday
- missed_escalation: crooked-chandelier-warranty, spanish-speaking-electrician

## Costly errors in `eval-fernhollow-2-sealed-20261109-165629-p2`

- missed_safety: branch-pulled-service-wire, home-inspector-scorched-breaker, toddler-pried-off-cover, toilet-overflow-through-light, vacuum-blue-flash-last-sunday
- missed_escalation: crooked-chandelier-warranty, spanish-speaking-electrician, two-calls-no-callback-dead-outlets

## Costly errors in `eval-fernhollow-2-sealed-20261109-173216-p3`

- missed_safety: branch-pulled-service-wire, home-inspector-scorched-breaker, toddler-pried-off-cover, toilet-overflow-through-light, vacuum-blue-flash-last-sunday
- missed_escalation: crooked-chandelier-warranty, spanish-speaking-electrician

## What this cannot tell you

- The costs are assumptions. The counts per kind are given so other costs can be applied.
- The mix of the evaluation sets is not a real inbox: they hold more messages that should escalate than a business would see, which favours escalating everything.
- An escalated message is assumed to be handled well by a person, and a draft that should not exist is costed once, not by what happens if it is approved.
