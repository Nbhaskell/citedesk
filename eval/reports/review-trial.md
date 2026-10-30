# Reviewer trial

> SYNTHETIC DATA. Every customer and message here is invented. One reviewer, who also built the system.

Protocol: `docs/REVIEW_TRIAL.md`, written before the trial. No pass mark.

## Review time (the app's own `review_seconds`)

| Drafts | n | Median | p90 | Range |
|---|---|---|---|---|
| All scored | 20 | 37 s | 81 s | 13 to 96 s |
| Ordinary | 14 | 40 s | 82 s | 21 to 96 s |
| With a planted problem | 6 | 32 s | 81 s | 13 to 81 s |

## Decisions

| Drafts | n | Approved | Edited and approved | Rejected | Escalated | Not reviewed |
|---|---|---|---|---|---|---|
| Ordinary | 14 | 11 | 0 | 3 | 0 | 0 |
| With a planted problem | 6 | 6 | 0 | 0 | 0 | 0 |

## Planted problems

The reviewer caught the planted problem on **0 of 6** reviewed drafts with one (6 planted). A count this small gives a wide exact 95% interval: 0.00 to 0.46 as a share. A draft counts as caught if it was rejected, escalated, or edited so the planted text is gone.

| Position | Item | Kind | Decision | Seconds | Caught |
|---|---|---|---|---|---|
| 6 | `service-hidden-leak-detection` | wrong_service_price | approve | 29 | no |
| 8 | `vague-need-a-plumber` | setup_disclosure | approve | 81 | no |
| 11 | `cancel-no-reference` | unlisted_credit | approve | 13 | no |
| 13 | `booking-drain-complete-details` | wrong_name | approve | 26 | no |
| 15 | `oos-septic-tank-full` | invented_perk | approve | 34 | no |
| 23 | `vague-toilet-weird-noise` | soft_commitment | approve | 42 | no |

## What this cannot tell you

- One reviewer who also built the system: they know the screens and what the checks do, so times and the catch count flatter the system.
- The reviewer already knew some kinds of planted problem from earlier discussion of the weaknesses, so was not naive to them.
- A high share of bad drafts (6 of 20) makes people more careful than they would be when problems are rare: the catch count is probably an upper bound.
- Six planted drafts cannot give a rate; read the counts.
- Invented messages and an invented business: this shows how the screens work for one person, not how a real front desk would cope.
- It does not measure whether the model reads messages correctly (the intent accuracy in `eval/reports/`).
