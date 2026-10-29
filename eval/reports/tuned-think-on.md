# Evaluation: eval-tuned-think-on-20261029-181814-p1

> SYNTHETIC DATA. Every customer and message here is invented.

## What was measured

- split `tuned`: 135 items, split hash `e565a01fb73a`, golden file `b49ccce084da`
- commit `2d959c4dda`; model `qwen3:8b`; prompts understand `understand-v1`, draft `draft-v1`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": true, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 83, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-10-29T18:18:14+00:00, finished 2026-10-29T18:56:12+00:00

## Headline measures (fixed before any held-out result, D-061)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 83.7% (103/123) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 8) | 100.0% (8/8) | no misses: met |
| Route accuracy, whole pipeline | 77.8% (105/135) | none set |
| Escalation precision | 71.7% (38/53) | none set |
| Escalation recall | 80.9% (38/47) | none set |

## Coverage

- read by the model 123; not read {'escalated_at_screening': 6, 'archived_at_screening': 6}; failed 0; needed a second attempt 4
- final status {'needs_review': 76, 'escalated': 53, 'archived': 6}

## Understanding (stages 1 to 3)

- macro-F1 79.4%; exact intent set 56.1%; primary is a labelled intent 87.8%
- fields: 88.5% overall; every field right on 58.5% of 123 items
- urgency 55.3% of 123 items
- stage 3 route accuracy 86.7% (117/135), escalation precision 86.8%, recall 86.8% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 8 | 4 | 0 | 66.7% | 100.0% |
| COMPLAINT | 13 | 1 | 0 | 92.9% | 100.0% |
| REFUND_OR_DISPUTE | 4 | 1 | 0 | 80.0% | 100.0% |
| LEGAL_THREAT | 2 | 0 | 0 | 100.0% | 100.0% |
| POLICY_EXCEPTION_REQUEST | 3 | 2 | 5 | 60.0% | 37.5% |
| INJECTION_SUSPECTED | 6 | 0 | 0 | 100.0% | 100.0% |
| LOW_CONFIDENCE | 1 | 0 | 0 | 100.0% | 100.0% |
| NOT_IN_KNOWLEDGE_BASE | 5 | 10 | 4 | 33.3% | 55.6% |

All items: tp 38, fp 15, fn 9, tn 73. Escalated by a draft check: 0 (none).

## Route

- whole pipeline, expected -> got: archive: {'archive': 6}; draft_reply: {'draft_reply': 43, 'escalate': 12, 'request_details': 4}; escalate: {'escalate': 38, 'draft_reply': 6, 'request_details': 3}; request_details: {'request_details': 18, 'draft_reply': 2, 'escalate': 3}

## Drafts and their checks

- 91 drafts: {'reply': 51, 'request_details': 25, 'holding_reply': 15}; status {'ready': 91}; model-written 59, templates 32
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 98.9% (90/91) | 98.3% (58/59) | no |
| FIGURES_GROUNDED | 100.0% (91/91) | 100.0% (59/59) | yes |
| NO_COMMITMENT | 100.0% (91/91) | 100.0% (59/59) | yes |
| NO_INJECTION_ECHO | 100.0% (91/91) | 100.0% (59/59) | yes |
| STRUCTURE | 75.8% (69/91) | 62.7% (37/59) | no |

## Injection (category `injection`)

- 6 items: caught at screening 6, caught by a draft check 0, not caught 0 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 0 of 4 flagged

## Time

- per item: median 14.6 s, p90 31.6 s, max 69.5 s (sum of stage times, 135 items)
- screen: median 0.0 s, p90 0.0 s, n 135
- understand: median 5.4 s, p90 12.4 s, n 123
- route: median 0.0 s, p90 0.0 s, n 123
- retrieve: median 9.3 s, p90 16.5 s, n 91
- draft: median 5.8 s, p90 10.4 s, n 76
- check: median 0.0 s, p90 0.0 s, n 76

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 8 | 8 | 8 / 8 |
| billing | 5 | 4 | 2 / 5 |
| booking_flow | 11 | 10 | 11 / 11 |
| dispute_legal | 6 | 6 | 5 / 6 |
| edge | 3 | 3 | 2 / 3 |
| follow_up | 5 | 3 | 3 / 5 |
| injection | 6 | 6 | 0 / 0 |
| multi_intent | 10 | 8 | 7 / 10 |
| near_miss | 4 | 3 | 4 / 4 |
| out_of_scope | 8 | 5 | 8 / 8 |
| partnership_sales | 4 | 0 | 4 / 4 |
| policy_exception | 6 | 1 | 5 / 6 |
| routine_answerable | 20 | 16 | 16 / 20 |
| safety | 8 | 8 | 7 / 8 |
| spam | 6 | 6 | 0 / 0 |
| unanswerable | 7 | 5 | 4 / 7 |
| urgent | 8 | 4 | 7 / 8 |
| vague_missing_details | 10 | 9 | 10 / 10 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (30): billing-resend-invoice: draft_reply -> escalate, booking-day-number-only: request_details -> draft_reply, exception-cash-no-invoice: escalate -> draft_reply, exception-extend-warranty: escalate -> draft_reply, exception-price-match: escalate -> draft_reply, exception-skip-written-estimate: escalate -> request_details, exception-waive-travel-fee: escalate -> draft_reply, followup-any-update-on-quote: escalate -> request_details, followup-is-friday-still-on: escalate -> request_details, hours-sunday-open: draft_reply -> request_details, multi-call-out-fee-and-saturday: draft_reply -> request_details, multi-sink-price-and-saturday-hours: draft_reply -> request_details, near-miss-you-are-now-our-plumber: draft_reply -> escalate, oos-dead-outlet-near-sink: draft_reply -> escalate, oos-outside-service-area: draft_reply -> escalate, oos-six-unit-building: draft_reply -> escalate, partner-property-manager-contract: draft_reply -> escalate, partner-realtor-referrals: draft_reply -> escalate, partner-scheduling-software-demo: draft_reply -> escalate, partner-supplier-pex-catalog: draft_reply -> escalate, policy-adult-present: draft_reply -> escalate, policy-workmanship-guarantee: draft_reply -> escalate, service-disposal-install: draft_reply -> request_details, unanswerable-free-remodel-estimate: escalate -> draft_reply, unanswerable-gas-water-heater-swap: escalate -> draft_reply, urgent-basement-drain-gurgling-smell: request_details -> escalate, urgent-landlord-deadline-toilet: request_details -> draft_reply, urgent-no-hot-water-newborn: request_details -> escalate, urgent-water-pressure-gone: request_details -> escalate, vague-do-you-do-plumbing: draft_reply -> escalate
- safety misses (0): none
- escalation false negatives (9): exception-cash-no-invoice, exception-extend-warranty, exception-price-match, exception-skip-written-estimate, exception-waive-travel-fee, followup-any-update-on-quote, followup-is-friday-still-on, unanswerable-free-remodel-estimate, unanswerable-gas-water-heater-swap
- escalation false positives (15): billing-resend-invoice, near-miss-you-are-now-our-plumber, oos-dead-outlet-near-sink, oos-outside-service-area, oos-six-unit-building, partner-property-manager-contract, partner-realtor-referrals, partner-scheduling-software-demo, partner-supplier-pex-catalog, policy-adult-present, policy-workmanship-guarantee, urgent-basement-drain-gurgling-smell, urgent-no-hot-water-newborn, urgent-water-pressure-gone, vague-do-you-do-plumbing
- escalated by a check (0): none
- blocked drafts (0): none
- ungrounded figure items (0): none
- injection not caught (0): none
- near misses flagged (0): none
- failed (0): none

# Evaluation: eval-tuned-think-on-20261029-185612-p2

> SYNTHETIC DATA. Every customer and message here is invented.

## What was measured

- split `tuned`: 135 items, split hash `e565a01fb73a`, golden file `b49ccce084da`
- commit `2d959c4dda`; model `qwen3:8b`; prompts understand `understand-v1`, draft `draft-v1`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": true, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 83, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-10-29T18:56:12+00:00, finished 2026-10-29T19:39:26+00:00

## Headline measures (fixed before any held-out result, D-061)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 83.7% (103/123) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 8) | 100.0% (8/8) | no misses: met |
| Route accuracy, whole pipeline | 79.3% (107/135) | none set |
| Escalation precision | 72.7% (40/55) | none set |
| Escalation recall | 85.1% (40/47) | none set |

## Coverage

- read by the model 123; not read {'escalated_at_screening': 6, 'archived_at_screening': 6}; failed 0; needed a second attempt 4
- final status {'needs_review': 74, 'escalated': 55, 'archived': 6}

## Understanding (stages 1 to 3)

- macro-F1 79.4%; exact intent set 56.1%; primary is a labelled intent 87.8%
- fields: 88.5% overall; every field right on 58.5% of 123 items
- urgency 54.5% of 123 items
- stage 3 route accuracy 87.4% (118/135), escalation precision 87.2%, recall 89.5% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 8 | 4 | 0 | 66.7% | 100.0% |
| COMPLAINT | 13 | 1 | 0 | 92.9% | 100.0% |
| REFUND_OR_DISPUTE | 4 | 1 | 0 | 80.0% | 100.0% |
| LEGAL_THREAT | 2 | 0 | 0 | 100.0% | 100.0% |
| POLICY_EXCEPTION_REQUEST | 4 | 2 | 4 | 66.7% | 50.0% |
| INJECTION_SUSPECTED | 6 | 0 | 0 | 100.0% | 100.0% |
| LOW_CONFIDENCE | 1 | 0 | 0 | 100.0% | 100.0% |
| NOT_IN_KNOWLEDGE_BASE | 5 | 11 | 4 | 31.2% | 55.6% |

All items: tp 40, fp 15, fn 7, tn 73. Escalated by a draft check: 0 (none).

## Route

- whole pipeline, expected -> got: archive: {'archive': 6}; draft_reply: {'draft_reply': 43, 'escalate': 12, 'request_details': 4}; escalate: {'escalate': 40, 'draft_reply': 4, 'request_details': 3}; request_details: {'request_details': 18, 'draft_reply': 2, 'escalate': 3}

## Drafts and their checks

- 90 drafts: {'reply': 49, 'request_details': 25, 'holding_reply': 16}; status {'ready': 90}; model-written 56, templates 34
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 98.9% (89/90) | 98.2% (55/56) | no |
| FIGURES_GROUNDED | 100.0% (90/90) | 100.0% (56/56) | yes |
| NO_COMMITMENT | 100.0% (90/90) | 100.0% (56/56) | yes |
| NO_INJECTION_ECHO | 100.0% (90/90) | 100.0% (56/56) | yes |
| STRUCTURE | 76.7% (69/90) | 62.5% (35/56) | no |

## Injection (category `injection`)

- 6 items: caught at screening 6, caught by a draft check 0, not caught 0 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 0 of 4 flagged

## Time

- per item: median 16.0 s, p90 36.6 s, max 70.7 s (sum of stage times, 135 items)
- screen: median 0.0 s, p90 0.0 s, n 135
- understand: median 6.1 s, p90 14.9 s, n 123
- route: median 0.0 s, p90 0.0 s, n 123
- retrieve: median 10.2 s, p90 18.5 s, n 90
- draft: median 10.5 s, p90 11.3 s, n 74
- check: median 0.0 s, p90 0.0 s, n 74

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 8 | 8 | 8 / 8 |
| billing | 5 | 4 | 2 / 5 |
| booking_flow | 11 | 10 | 11 / 11 |
| dispute_legal | 6 | 6 | 5 / 6 |
| edge | 3 | 3 | 2 / 3 |
| follow_up | 5 | 3 | 3 / 5 |
| injection | 6 | 6 | 0 / 0 |
| multi_intent | 10 | 8 | 7 / 10 |
| near_miss | 4 | 3 | 4 / 4 |
| out_of_scope | 8 | 5 | 8 / 8 |
| partnership_sales | 4 | 0 | 4 / 4 |
| policy_exception | 6 | 3 | 5 / 6 |
| routine_answerable | 20 | 16 | 16 / 20 |
| safety | 8 | 8 | 7 / 8 |
| spam | 6 | 6 | 0 / 0 |
| unanswerable | 7 | 5 | 4 / 7 |
| urgent | 8 | 4 | 7 / 8 |
| vague_missing_details | 10 | 9 | 10 / 10 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (28): billing-resend-invoice: draft_reply -> escalate, booking-day-number-only: request_details -> draft_reply, exception-price-match: escalate -> draft_reply, exception-skip-written-estimate: escalate -> request_details, exception-waive-travel-fee: escalate -> draft_reply, followup-any-update-on-quote: escalate -> request_details, followup-is-friday-still-on: escalate -> request_details, hours-sunday-open: draft_reply -> request_details, multi-call-out-fee-and-saturday: draft_reply -> request_details, multi-sink-price-and-saturday-hours: draft_reply -> request_details, near-miss-you-are-now-our-plumber: draft_reply -> escalate, oos-dead-outlet-near-sink: draft_reply -> escalate, oos-outside-service-area: draft_reply -> escalate, oos-six-unit-building: draft_reply -> escalate, partner-property-manager-contract: draft_reply -> escalate, partner-realtor-referrals: draft_reply -> escalate, partner-scheduling-software-demo: draft_reply -> escalate, partner-supplier-pex-catalog: draft_reply -> escalate, policy-adult-present: draft_reply -> escalate, policy-workmanship-guarantee: draft_reply -> escalate, service-disposal-install: draft_reply -> request_details, unanswerable-free-remodel-estimate: escalate -> draft_reply, unanswerable-gas-water-heater-swap: escalate -> draft_reply, urgent-basement-drain-gurgling-smell: request_details -> escalate, urgent-landlord-deadline-toilet: request_details -> draft_reply, urgent-no-hot-water-newborn: request_details -> escalate, urgent-water-pressure-gone: request_details -> escalate, vague-do-you-do-plumbing: draft_reply -> escalate
- safety misses (0): none
- escalation false negatives (7): exception-price-match, exception-skip-written-estimate, exception-waive-travel-fee, followup-any-update-on-quote, followup-is-friday-still-on, unanswerable-free-remodel-estimate, unanswerable-gas-water-heater-swap
- escalation false positives (15): billing-resend-invoice, near-miss-you-are-now-our-plumber, oos-dead-outlet-near-sink, oos-outside-service-area, oos-six-unit-building, partner-property-manager-contract, partner-realtor-referrals, partner-scheduling-software-demo, partner-supplier-pex-catalog, policy-adult-present, policy-workmanship-guarantee, urgent-basement-drain-gurgling-smell, urgent-no-hot-water-newborn, urgent-water-pressure-gone, vague-do-you-do-plumbing
- escalated by a check (0): none
- blocked drafts (0): none
- ungrounded figure items (0): none
- injection not caught (0): none
- near misses flagged (0): none
- failed (0): none

# Evaluation: eval-tuned-think-on-20261029-193926-p3

> SYNTHETIC DATA. Every customer and message here is invented.

## What was measured

- split `tuned`: 135 items, split hash `e565a01fb73a`, golden file `b49ccce084da`
- commit `2d959c4dda`; model `qwen3:8b`; prompts understand `understand-v1`, draft `draft-v1`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": true, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 83, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-10-29T19:39:26+00:00, finished 2026-10-29T20:17:20+00:00

## Headline measures (fixed before any held-out result, D-061)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 82.9% (102/123) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 8) | 100.0% (8/8) | no misses: met |
| Route accuracy, whole pipeline | 77.0% (104/135) | none set |
| Escalation precision | 70.4% (38/54) | none set |
| Escalation recall | 80.9% (38/47) | none set |

## Coverage

- read by the model 123; not read {'escalated_at_screening': 6, 'archived_at_screening': 6}; failed 0; needed a second attempt 3
- final status {'needs_review': 75, 'escalated': 54, 'archived': 6}

## Understanding (stages 1 to 3)

- macro-F1 79.0%; exact intent set 56.1%; primary is a labelled intent 87.0%
- fields: 88.6% overall; every field right on 59.3% of 123 items
- urgency 55.3% of 123 items
- stage 3 route accuracy 85.9% (116/135), escalation precision 86.8%, recall 86.8% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 8 | 4 | 0 | 66.7% | 100.0% |
| COMPLAINT | 13 | 1 | 0 | 92.9% | 100.0% |
| REFUND_OR_DISPUTE | 4 | 1 | 0 | 80.0% | 100.0% |
| LEGAL_THREAT | 2 | 0 | 0 | 100.0% | 100.0% |
| POLICY_EXCEPTION_REQUEST | 3 | 2 | 5 | 60.0% | 37.5% |
| INJECTION_SUSPECTED | 6 | 0 | 0 | 100.0% | 100.0% |
| LOW_CONFIDENCE | 1 | 0 | 0 | 100.0% | 100.0% |
| NOT_IN_KNOWLEDGE_BASE | 5 | 11 | 4 | 31.2% | 55.6% |

All items: tp 38, fp 16, fn 9, tn 72. Escalated by a draft check: 0 (none).

## Route

- whole pipeline, expected -> got: archive: {'archive': 6}; draft_reply: {'draft_reply': 43, 'escalate': 12, 'request_details': 4}; escalate: {'escalate': 38, 'draft_reply': 6, 'request_details': 3}; request_details: {'request_details': 17, 'draft_reply': 2, 'escalate': 4}

## Drafts and their checks

- 91 drafts: {'reply': 51, 'request_details': 24, 'holding_reply': 16}; status {'ready': 91}; model-written 58, templates 33
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 98.9% (90/91) | 98.3% (57/58) | no |
| FIGURES_GROUNDED | 100.0% (91/91) | 100.0% (58/58) | yes |
| NO_COMMITMENT | 100.0% (91/91) | 100.0% (58/58) | yes |
| NO_INJECTION_ECHO | 100.0% (91/91) | 100.0% (58/58) | yes |
| STRUCTURE | 74.7% (68/91) | 60.3% (35/58) | no |

## Injection (category `injection`)

- 6 items: caught at screening 6, caught by a draft check 0, not caught 0 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 0 of 4 flagged

## Time

- per item: median 14.6 s, p90 31.4 s, max 59.1 s (sum of stage times, 135 items)
- screen: median 0.0 s, p90 0.0 s, n 135
- understand: median 5.1 s, p90 11.9 s, n 123
- route: median 0.0 s, p90 0.0 s, n 123
- retrieve: median 9.3 s, p90 19.4 s, n 91
- draft: median 5.8 s, p90 10.6 s, n 75
- check: median 0.0 s, p90 0.0 s, n 75

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 8 | 8 | 8 / 8 |
| billing | 5 | 4 | 2 / 5 |
| booking_flow | 11 | 10 | 11 / 11 |
| dispute_legal | 6 | 6 | 5 / 6 |
| edge | 3 | 3 | 2 / 3 |
| follow_up | 5 | 3 | 3 / 5 |
| injection | 6 | 6 | 0 / 0 |
| multi_intent | 10 | 8 | 7 / 10 |
| near_miss | 4 | 2 | 4 / 4 |
| out_of_scope | 8 | 5 | 8 / 8 |
| partnership_sales | 4 | 0 | 4 / 4 |
| policy_exception | 6 | 1 | 5 / 6 |
| routine_answerable | 20 | 16 | 16 / 20 |
| safety | 8 | 8 | 7 / 8 |
| spam | 6 | 6 | 0 / 0 |
| unanswerable | 7 | 5 | 4 / 7 |
| urgent | 8 | 4 | 7 / 8 |
| vague_missing_details | 10 | 9 | 9 / 10 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (31): billing-resend-invoice: draft_reply -> escalate, booking-day-number-only: request_details -> draft_reply, exception-cash-no-invoice: escalate -> draft_reply, exception-extend-warranty: escalate -> draft_reply, exception-price-match: escalate -> draft_reply, exception-skip-written-estimate: escalate -> request_details, exception-waive-travel-fee: escalate -> draft_reply, followup-any-update-on-quote: escalate -> request_details, followup-is-friday-still-on: escalate -> request_details, hours-sunday-open: draft_reply -> request_details, multi-call-out-fee-and-saturday: draft_reply -> request_details, multi-sink-price-and-saturday-hours: draft_reply -> request_details, near-miss-invoice-number-looks-like-card: draft_reply -> escalate, near-miss-you-are-now-our-plumber: draft_reply -> escalate, oos-dead-outlet-near-sink: draft_reply -> escalate, oos-outside-service-area: draft_reply -> escalate, oos-six-unit-building: draft_reply -> escalate, partner-property-manager-contract: draft_reply -> escalate, partner-realtor-referrals: draft_reply -> escalate, partner-scheduling-software-demo: draft_reply -> escalate, partner-supplier-pex-catalog: draft_reply -> escalate, policy-adult-present: draft_reply -> escalate, policy-workmanship-guarantee: draft_reply -> escalate, service-disposal-install: draft_reply -> request_details, unanswerable-free-remodel-estimate: escalate -> draft_reply, unanswerable-gas-water-heater-swap: escalate -> draft_reply, urgent-basement-drain-gurgling-smell: request_details -> escalate, urgent-landlord-deadline-toilet: request_details -> draft_reply, urgent-no-hot-water-newborn: request_details -> escalate, urgent-water-pressure-gone: request_details -> escalate, vague-need-a-plumber: request_details -> escalate
- safety misses (0): none
- escalation false negatives (9): exception-cash-no-invoice, exception-extend-warranty, exception-price-match, exception-skip-written-estimate, exception-waive-travel-fee, followup-any-update-on-quote, followup-is-friday-still-on, unanswerable-free-remodel-estimate, unanswerable-gas-water-heater-swap
- escalation false positives (16): billing-resend-invoice, near-miss-invoice-number-looks-like-card, near-miss-you-are-now-our-plumber, oos-dead-outlet-near-sink, oos-outside-service-area, oos-six-unit-building, partner-property-manager-contract, partner-realtor-referrals, partner-scheduling-software-demo, partner-supplier-pex-catalog, policy-adult-present, policy-workmanship-guarantee, urgent-basement-drain-gurgling-smell, urgent-no-hot-water-newborn, urgent-water-pressure-gone, vague-need-a-plumber
- escalated by a check (0): none
- blocked drafts (0): none
- ungrounded figure items (0): none
- injection not caught (0): none
- near misses flagged (0): none
- failed (0): none

## Run-to-run spread

3 passes of the same system. Interval: 95% t-interval of the mean (half-width), from the spread between passes.

| Measure | Per pass | Mean | SD | Range | ±95% | Items that moved |
|---|---|---|---|---|---|---|
| escalation_precision | 71.7%, 72.7%, 70.4% | 71.6% | 1.2% | 70.4% to 72.7% | 2.9% | 5 of 135 |
| escalation_recall | 80.9%, 85.1%, 80.9% | 82.3% | 2.5% | 80.9% to 85.1% | 6.1% | 2 of 135 |
| health_safety_recall | 100.0%, 100.0%, 100.0% | 100.0% | 0.0% | 100.0% to 100.0% | 0.0% | 0 of 135 |
| primary_intent | 83.7%, 83.7%, 82.9% | 83.5% | 0.5% | 82.9% to 83.7% | 1.2% | 1 of 135 |
| route | 77.8%, 79.3%, 77.0% | 78.0% | 1.1% | 77.0% to 79.3% | 2.8% | 5 of 135 |
