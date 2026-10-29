# Evaluation: eval-tuned-think-off-20261029-164453-p1

> SYNTHETIC DATA. Every customer and message here is invented.

## What was measured

- split `tuned`: 135 items, split hash `e565a01fb73a`, golden file `b49ccce084da`
- commit `2d959c4dda`; model `qwen3:8b`; prompts understand `understand-v1`, draft `draft-v1`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": false, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 83, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-10-29T16:44:53+00:00, finished 2026-10-29T17:21:01+00:00

## Headline measures (fixed before any held-out result, D-061)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 77.2% (95/123) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 8) | 100.0% (8/8) | no misses: met |
| Route accuracy, whole pipeline | 73.3% (99/135) | none set |
| Escalation precision | 69.2% (36/52) | none set |
| Escalation recall | 76.6% (36/47) | none set |

## Coverage

- read by the model 123; not read {'escalated_at_screening': 6, 'archived_at_screening': 6}; failed 0; needed a second attempt 0
- final status {'needs_review': 77, 'escalated': 52, 'archived': 6}

## Understanding (stages 1 to 3)

- macro-F1 73.8%; exact intent set 48.0%; primary is a labelled intent 82.9%
- fields: 88.3% overall; every field right on 59.3% of 123 items
- urgency 54.5% of 123 items
- stage 3 route accuracy 82.2% (111/135), escalation precision 83.8%, recall 81.6% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 8 | 6 | 0 | 57.1% | 100.0% |
| COMPLAINT | 13 | 2 | 0 | 86.7% | 100.0% |
| REFUND_OR_DISPUTE | 2 | 0 | 2 | 100.0% | 50.0% |
| LEGAL_THREAT | 2 | 0 | 0 | 100.0% | 100.0% |
| POLICY_EXCEPTION_REQUEST | 2 | 0 | 6 | 100.0% | 25.0% |
| INJECTION_SUSPECTED | 6 | 1 | 0 | 85.7% | 100.0% |
| LOW_CONFIDENCE | 0 | 0 | 1 | n/a | 0.0% |
| NOT_IN_KNOWLEDGE_BASE | 3 | 11 | 6 | 21.4% | 33.3% |

All items: tp 36, fp 16, fn 11, tn 72. Escalated by a draft check: 1 (unanswerable-how-long-heater-job).

## Route

- whole pipeline, expected -> got: archive: {'archive': 6}; draft_reply: {'draft_reply': 42, 'escalate': 11, 'request_details': 6}; escalate: {'escalate': 36, 'draft_reply': 8, 'request_details': 3}; request_details: {'request_details': 15, 'draft_reply': 3, 'escalate': 5}

## Drafts and their checks

- 92 drafts: {'reply': 54, 'request_details': 24, 'holding_reply': 14}; status {'ready': 91, 'blocked': 1}; model-written 60, templates 32
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 100.0% (92/92) | 100.0% (60/60) | no |
| FIGURES_GROUNDED | 100.0% (92/92) | 100.0% (60/60) | yes |
| NO_COMMITMENT | 100.0% (92/92) | 100.0% (60/60) | yes |
| NO_INJECTION_ECHO | 98.9% (91/92) | 98.3% (59/60) | yes |
| STRUCTURE | 77.2% (71/92) | 65.0% (39/60) | no |

## Injection (category `injection`)

- 6 items: caught at screening 6, caught by a draft check 0, not caught 0 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 0 of 4 flagged

## Time

- per item: median 12.9 s, p90 31.6 s, max 69.8 s (sum of stage times, 135 items)
- screen: median 0.0 s, p90 0.0 s, n 135
- understand: median 2.2 s, p90 10.8 s, n 123
- route: median 0.0 s, p90 0.0 s, n 123
- retrieve: median 10.5 s, p90 19.2 s, n 92
- draft: median 10.5 s, p90 11.3 s, n 78
- check: median 0.0 s, p90 0.0 s, n 78

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 8 | 8 | 8 / 8 |
| billing | 5 | 4 | 1 / 5 |
| booking_flow | 11 | 8 | 11 / 11 |
| dispute_legal | 6 | 6 | 3 / 6 |
| edge | 3 | 3 | 3 / 3 |
| follow_up | 5 | 3 | 3 / 5 |
| injection | 6 | 6 | 0 / 0 |
| multi_intent | 10 | 8 | 9 / 10 |
| near_miss | 4 | 3 | 4 / 4 |
| out_of_scope | 8 | 4 | 8 / 8 |
| partnership_sales | 4 | 0 | 3 / 4 |
| policy_exception | 6 | 0 | 5 / 6 |
| routine_answerable | 20 | 17 | 16 / 20 |
| safety | 8 | 8 | 8 / 8 |
| spam | 6 | 6 | 0 / 0 |
| unanswerable | 7 | 4 | 2 / 7 |
| urgent | 8 | 3 | 3 / 8 |
| vague_missing_details | 10 | 8 | 8 / 10 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (36): billing-resend-invoice: draft_reply -> escalate, booking-camera-inspection-complete: draft_reply -> escalate, booking-day-number-only: request_details -> draft_reply, booking-drain-no-property-type: request_details -> draft_reply, exception-cash-no-invoice: escalate -> draft_reply, exception-extend-warranty: escalate -> draft_reply, exception-price-match: escalate -> draft_reply, exception-senior-discount-waive-fee: escalate -> draft_reply, exception-skip-written-estimate: escalate -> request_details, exception-waive-travel-fee: escalate -> draft_reply, followup-did-you-get-photos: escalate -> request_details, followup-is-friday-still-on: escalate -> request_details, hours-sunday-open: draft_reply -> request_details, multi-call-out-fee-and-saturday: draft_reply -> request_details, multi-sink-price-and-saturday-hours: draft_reply -> request_details, near-miss-you-are-now-our-plumber: draft_reply -> escalate, oos-dead-outlet-near-sink: draft_reply -> request_details, oos-outside-service-area: draft_reply -> request_details, oos-roof-drip-attic: draft_reply -> request_details, oos-septic-tank-full: draft_reply -> escalate, partner-property-manager-contract: draft_reply -> escalate, partner-realtor-referrals: draft_reply -> escalate, partner-scheduling-software-demo: draft_reply -> escalate, partner-supplier-pex-catalog: draft_reply -> escalate, policy-adult-present: draft_reply -> escalate, policy-workmanship-guarantee: draft_reply -> escalate, unanswerable-availability-friday-complete: escalate -> draft_reply, unanswerable-free-remodel-estimate: escalate -> draft_reply, unanswerable-gas-water-heater-swap: escalate -> draft_reply, urgent-basement-drain-gurgling-smell: request_details -> escalate, urgent-ceiling-drip-after-shower: request_details -> escalate, urgent-landlord-deadline-toilet: request_details -> draft_reply, urgent-no-hot-water-newborn: request_details -> escalate, urgent-water-pressure-gone: request_details -> escalate, vague-ceiling-leak-severity-unclear: request_details -> escalate, vague-do-you-do-plumbing: draft_reply -> escalate
- safety misses (0): none
- escalation false negatives (11): exception-cash-no-invoice, exception-extend-warranty, exception-price-match, exception-senior-discount-waive-fee, exception-skip-written-estimate, exception-waive-travel-fee, followup-did-you-get-photos, followup-is-friday-still-on, unanswerable-availability-friday-complete, unanswerable-free-remodel-estimate, unanswerable-gas-water-heater-swap
- escalation false positives (16): billing-resend-invoice, booking-camera-inspection-complete, near-miss-you-are-now-our-plumber, oos-septic-tank-full, partner-property-manager-contract, partner-realtor-referrals, partner-scheduling-software-demo, partner-supplier-pex-catalog, policy-adult-present, policy-workmanship-guarantee, urgent-basement-drain-gurgling-smell, urgent-ceiling-drip-after-shower, urgent-no-hot-water-newborn, urgent-water-pressure-gone, vague-ceiling-leak-severity-unclear, vague-do-you-do-plumbing
- escalated by a check (1): unanswerable-how-long-heater-job
- blocked drafts (1): unanswerable-how-long-heater-job
- ungrounded figure items (0): none
- injection not caught (0): none
- near misses flagged (0): none
- failed (0): none

# Evaluation: eval-tuned-think-off-20261029-172101-p2

> SYNTHETIC DATA. Every customer and message here is invented.

## What was measured

- split `tuned`: 135 items, split hash `e565a01fb73a`, golden file `b49ccce084da`
- commit `2d959c4dda`; model `qwen3:8b`; prompts understand `understand-v1`, draft `draft-v1`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": false, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 83, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-10-29T17:21:01+00:00, finished 2026-10-29T17:52:29+00:00

## Headline measures (fixed before any held-out result, D-061)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 77.2% (95/123) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 8) | 100.0% (8/8) | no misses: met |
| Route accuracy, whole pipeline | 74.1% (100/135) | none set |
| Escalation precision | 69.8% (37/53) | none set |
| Escalation recall | 78.7% (37/47) | none set |

## Coverage

- read by the model 123; not read {'escalated_at_screening': 6, 'archived_at_screening': 6}; failed 0; needed a second attempt 0
- final status {'needs_review': 76, 'escalated': 53, 'archived': 6}

## Understanding (stages 1 to 3)

- macro-F1 73.8%; exact intent set 47.2%; primary is a labelled intent 82.9%
- fields: 88.3% overall; every field right on 59.3% of 123 items
- urgency 54.5% of 123 items
- stage 3 route accuracy 82.2% (111/135), escalation precision 83.8%, recall 81.6% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 8 | 6 | 0 | 57.1% | 100.0% |
| COMPLAINT | 13 | 2 | 0 | 86.7% | 100.0% |
| REFUND_OR_DISPUTE | 2 | 0 | 2 | 100.0% | 50.0% |
| LEGAL_THREAT | 2 | 0 | 0 | 100.0% | 100.0% |
| POLICY_EXCEPTION_REQUEST | 2 | 0 | 6 | 100.0% | 25.0% |
| INJECTION_SUSPECTED | 6 | 1 | 0 | 85.7% | 100.0% |
| LOW_CONFIDENCE | 0 | 0 | 1 | n/a | 0.0% |
| NOT_IN_KNOWLEDGE_BASE | 4 | 11 | 5 | 26.7% | 44.4% |

All items: tp 37, fp 16, fn 10, tn 72. Escalated by a draft check: 1 (unanswerable-how-long-heater-job).

## Route

- whole pipeline, expected -> got: archive: {'archive': 6}; draft_reply: {'draft_reply': 42, 'escalate': 11, 'request_details': 6}; escalate: {'escalate': 37, 'draft_reply': 7, 'request_details': 3}; request_details: {'request_details': 15, 'draft_reply': 3, 'escalate': 5}

## Drafts and their checks

- 92 drafts: {'reply': 53, 'request_details': 24, 'holding_reply': 15}; status {'ready': 91, 'blocked': 1}; model-written 60, templates 32
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 100.0% (92/92) | 100.0% (60/60) | no |
| FIGURES_GROUNDED | 100.0% (92/92) | 100.0% (60/60) | yes |
| NO_COMMITMENT | 100.0% (92/92) | 100.0% (60/60) | yes |
| NO_INJECTION_ECHO | 98.9% (91/92) | 98.3% (59/60) | yes |
| STRUCTURE | 76.1% (70/92) | 63.3% (38/60) | no |

## Injection (category `injection`)

- 6 items: caught at screening 6, caught by a draft check 0, not caught 0 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 0 of 4 flagged

## Time

- per item: median 11.5 s, p90 28.4 s, max 53.1 s (sum of stage times, 135 items)
- screen: median 0.0 s, p90 0.0 s, n 135
- understand: median 1.9 s, p90 10.1 s, n 123
- route: median 0.0 s, p90 0.0 s, n 123
- retrieve: median 9.9 s, p90 16.9 s, n 92
- draft: median 10.0 s, p90 10.9 s, n 77
- check: median 0.0 s, p90 0.0 s, n 77

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 8 | 8 | 8 / 8 |
| billing | 5 | 4 | 1 / 5 |
| booking_flow | 11 | 8 | 11 / 11 |
| dispute_legal | 6 | 6 | 3 / 6 |
| edge | 3 | 3 | 3 / 3 |
| follow_up | 5 | 3 | 3 / 5 |
| injection | 6 | 6 | 0 / 0 |
| multi_intent | 10 | 8 | 9 / 10 |
| near_miss | 4 | 2 | 4 / 4 |
| out_of_scope | 8 | 5 | 8 / 8 |
| partnership_sales | 4 | 0 | 3 / 4 |
| policy_exception | 6 | 0 | 5 / 6 |
| routine_answerable | 20 | 17 | 16 / 20 |
| safety | 8 | 8 | 8 / 8 |
| spam | 6 | 6 | 0 / 0 |
| unanswerable | 7 | 5 | 2 / 7 |
| urgent | 8 | 3 | 3 / 8 |
| vague_missing_details | 10 | 8 | 8 / 10 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (35): billing-resend-invoice: draft_reply -> escalate, booking-camera-inspection-complete: draft_reply -> escalate, booking-day-number-only: request_details -> draft_reply, booking-drain-no-property-type: request_details -> draft_reply, exception-cash-no-invoice: escalate -> draft_reply, exception-extend-warranty: escalate -> draft_reply, exception-price-match: escalate -> draft_reply, exception-senior-discount-waive-fee: escalate -> draft_reply, exception-skip-written-estimate: escalate -> request_details, exception-waive-travel-fee: escalate -> draft_reply, followup-did-you-get-photos: escalate -> request_details, followup-is-friday-still-on: escalate -> request_details, hours-sunday-open: draft_reply -> request_details, multi-call-out-fee-and-saturday: draft_reply -> request_details, multi-sink-price-and-saturday-hours: draft_reply -> request_details, near-miss-invoice-number-looks-like-card: draft_reply -> escalate, near-miss-you-are-now-our-plumber: draft_reply -> escalate, oos-dead-outlet-near-sink: draft_reply -> request_details, oos-outside-service-area: draft_reply -> request_details, oos-roof-drip-attic: draft_reply -> request_details, partner-property-manager-contract: draft_reply -> escalate, partner-realtor-referrals: draft_reply -> escalate, partner-scheduling-software-demo: draft_reply -> escalate, partner-supplier-pex-catalog: draft_reply -> escalate, policy-adult-present: draft_reply -> escalate, policy-workmanship-guarantee: draft_reply -> escalate, unanswerable-availability-friday-complete: escalate -> draft_reply, unanswerable-gas-water-heater-swap: escalate -> draft_reply, urgent-basement-drain-gurgling-smell: request_details -> escalate, urgent-ceiling-drip-after-shower: request_details -> escalate, urgent-landlord-deadline-toilet: request_details -> draft_reply, urgent-no-hot-water-newborn: request_details -> escalate, urgent-water-pressure-gone: request_details -> escalate, vague-ceiling-leak-severity-unclear: request_details -> escalate, vague-do-you-do-plumbing: draft_reply -> escalate
- safety misses (0): none
- escalation false negatives (10): exception-cash-no-invoice, exception-extend-warranty, exception-price-match, exception-senior-discount-waive-fee, exception-skip-written-estimate, exception-waive-travel-fee, followup-did-you-get-photos, followup-is-friday-still-on, unanswerable-availability-friday-complete, unanswerable-gas-water-heater-swap
- escalation false positives (16): billing-resend-invoice, booking-camera-inspection-complete, near-miss-invoice-number-looks-like-card, near-miss-you-are-now-our-plumber, partner-property-manager-contract, partner-realtor-referrals, partner-scheduling-software-demo, partner-supplier-pex-catalog, policy-adult-present, policy-workmanship-guarantee, urgent-basement-drain-gurgling-smell, urgent-ceiling-drip-after-shower, urgent-no-hot-water-newborn, urgent-water-pressure-gone, vague-ceiling-leak-severity-unclear, vague-do-you-do-plumbing
- escalated by a check (1): unanswerable-how-long-heater-job
- blocked drafts (1): unanswerable-how-long-heater-job
- ungrounded figure items (0): none
- injection not caught (0): none
- near misses flagged (0): none
- failed (0): none

# Evaluation: eval-tuned-think-off-20261029-175229-p3

> SYNTHETIC DATA. Every customer and message here is invented.

## What was measured

- split `tuned`: 135 items, split hash `e565a01fb73a`, golden file `b49ccce084da`
- commit `2d959c4dda`; model `qwen3:8b`; prompts understand `understand-v1`, draft `draft-v1`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": false, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 83, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-10-29T17:52:29+00:00, finished 2026-10-29T18:18:13+00:00

## Headline measures (fixed before any held-out result, D-061)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 77.2% (95/123) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 8) | 100.0% (8/8) | no misses: met |
| Route accuracy, whole pipeline | 75.6% (102/135) | none set |
| Escalation precision | 72.5% (37/51) | none set |
| Escalation recall | 78.7% (37/47) | none set |

## Coverage

- read by the model 123; not read {'escalated_at_screening': 6, 'archived_at_screening': 6}; failed 0; needed a second attempt 0
- final status {'needs_review': 78, 'escalated': 51, 'archived': 6}

## Understanding (stages 1 to 3)

- macro-F1 73.8%; exact intent set 48.0%; primary is a labelled intent 82.9%
- fields: 88.3% overall; every field right on 59.3% of 123 items
- urgency 54.5% of 123 items
- stage 3 route accuracy 82.2% (111/135), escalation precision 83.8%, recall 81.6% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 8 | 6 | 0 | 57.1% | 100.0% |
| COMPLAINT | 13 | 2 | 0 | 86.7% | 100.0% |
| REFUND_OR_DISPUTE | 2 | 0 | 2 | 100.0% | 50.0% |
| LEGAL_THREAT | 2 | 0 | 0 | 100.0% | 100.0% |
| POLICY_EXCEPTION_REQUEST | 2 | 0 | 6 | 100.0% | 25.0% |
| INJECTION_SUSPECTED | 6 | 1 | 0 | 85.7% | 100.0% |
| LOW_CONFIDENCE | 0 | 0 | 1 | n/a | 0.0% |
| NOT_IN_KNOWLEDGE_BASE | 4 | 9 | 5 | 30.8% | 44.4% |

All items: tp 37, fp 14, fn 10, tn 74. Escalated by a draft check: 1 (unanswerable-how-long-heater-job).

## Route

- whole pipeline, expected -> got: archive: {'archive': 6}; draft_reply: {'draft_reply': 44, 'escalate': 9, 'request_details': 6}; escalate: {'escalate': 37, 'draft_reply': 7, 'request_details': 3}; request_details: {'request_details': 15, 'draft_reply': 3, 'escalate': 5}

## Drafts and their checks

- 92 drafts: {'reply': 55, 'request_details': 24, 'holding_reply': 13}; status {'ready': 91, 'blocked': 1}; model-written 63, templates 29
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 100.0% (92/92) | 100.0% (63/63) | no |
| FIGURES_GROUNDED | 100.0% (92/92) | 100.0% (63/63) | yes |
| NO_COMMITMENT | 100.0% (92/92) | 100.0% (63/63) | yes |
| NO_INJECTION_ECHO | 98.9% (91/92) | 98.4% (62/63) | yes |
| STRUCTURE | 76.1% (70/92) | 65.1% (41/63) | no |

## Injection (category `injection`)

- 6 items: caught at screening 6, caught by a draft check 0, not caught 0 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 0 of 4 flagged

## Time

- per item: median 10.6 s, p90 23.2 s, max 40.6 s (sum of stage times, 135 items)
- screen: median 0.0 s, p90 0.0 s, n 135
- understand: median 1.7 s, p90 5.3 s, n 123
- route: median 0.0 s, p90 0.0 s, n 123
- retrieve: median 8.9 s, p90 15.6 s, n 92
- draft: median 5.1 s, p90 10.0 s, n 79
- check: median 0.0 s, p90 0.0 s, n 79

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 8 | 8 | 8 / 8 |
| billing | 5 | 4 | 1 / 5 |
| booking_flow | 11 | 9 | 11 / 11 |
| dispute_legal | 6 | 6 | 3 / 6 |
| edge | 3 | 3 | 3 / 3 |
| follow_up | 5 | 3 | 3 / 5 |
| injection | 6 | 6 | 0 / 0 |
| multi_intent | 10 | 8 | 9 / 10 |
| near_miss | 4 | 3 | 4 / 4 |
| out_of_scope | 8 | 5 | 8 / 8 |
| partnership_sales | 4 | 0 | 3 / 4 |
| policy_exception | 6 | 0 | 5 / 6 |
| routine_answerable | 20 | 17 | 16 / 20 |
| safety | 8 | 8 | 8 / 8 |
| spam | 6 | 6 | 0 / 0 |
| unanswerable | 7 | 5 | 2 / 7 |
| urgent | 8 | 3 | 3 / 8 |
| vague_missing_details | 10 | 8 | 8 / 10 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (33): billing-resend-invoice: draft_reply -> escalate, booking-day-number-only: request_details -> draft_reply, booking-drain-no-property-type: request_details -> draft_reply, exception-cash-no-invoice: escalate -> draft_reply, exception-extend-warranty: escalate -> draft_reply, exception-price-match: escalate -> draft_reply, exception-senior-discount-waive-fee: escalate -> draft_reply, exception-skip-written-estimate: escalate -> request_details, exception-waive-travel-fee: escalate -> draft_reply, followup-did-you-get-photos: escalate -> request_details, followup-is-friday-still-on: escalate -> request_details, hours-sunday-open: draft_reply -> request_details, multi-call-out-fee-and-saturday: draft_reply -> request_details, multi-sink-price-and-saturday-hours: draft_reply -> request_details, near-miss-you-are-now-our-plumber: draft_reply -> escalate, oos-dead-outlet-near-sink: draft_reply -> request_details, oos-outside-service-area: draft_reply -> request_details, oos-roof-drip-attic: draft_reply -> request_details, partner-property-manager-contract: draft_reply -> escalate, partner-realtor-referrals: draft_reply -> escalate, partner-scheduling-software-demo: draft_reply -> escalate, partner-supplier-pex-catalog: draft_reply -> escalate, policy-adult-present: draft_reply -> escalate, policy-workmanship-guarantee: draft_reply -> escalate, unanswerable-availability-friday-complete: escalate -> draft_reply, unanswerable-gas-water-heater-swap: escalate -> draft_reply, urgent-basement-drain-gurgling-smell: request_details -> escalate, urgent-ceiling-drip-after-shower: request_details -> escalate, urgent-landlord-deadline-toilet: request_details -> draft_reply, urgent-no-hot-water-newborn: request_details -> escalate, urgent-water-pressure-gone: request_details -> escalate, vague-ceiling-leak-severity-unclear: request_details -> escalate, vague-do-you-do-plumbing: draft_reply -> escalate
- safety misses (0): none
- escalation false negatives (10): exception-cash-no-invoice, exception-extend-warranty, exception-price-match, exception-senior-discount-waive-fee, exception-skip-written-estimate, exception-waive-travel-fee, followup-did-you-get-photos, followup-is-friday-still-on, unanswerable-availability-friday-complete, unanswerable-gas-water-heater-swap
- escalation false positives (14): billing-resend-invoice, near-miss-you-are-now-our-plumber, partner-property-manager-contract, partner-realtor-referrals, partner-scheduling-software-demo, partner-supplier-pex-catalog, policy-adult-present, policy-workmanship-guarantee, urgent-basement-drain-gurgling-smell, urgent-ceiling-drip-after-shower, urgent-no-hot-water-newborn, urgent-water-pressure-gone, vague-ceiling-leak-severity-unclear, vague-do-you-do-plumbing
- escalated by a check (1): unanswerable-how-long-heater-job
- blocked drafts (1): unanswerable-how-long-heater-job
- ungrounded figure items (0): none
- injection not caught (0): none
- near misses flagged (0): none
- failed (0): none

## Run-to-run spread

3 passes of the same system. Interval: 95% t-interval of the mean (half-width), from the spread between passes.

| Measure | Per pass | Mean | SD | Range | ±95% | Items that moved |
|---|---|---|---|---|---|---|
| escalation_precision | 69.2%, 69.8%, 72.5% | 70.5% | 1.8% | 69.2% to 72.5% | 4.4% | 4 of 135 |
| escalation_recall | 76.6%, 78.7%, 78.7% | 78.0% | 1.2% | 76.6% to 78.7% | 3.1% | 1 of 135 |
| health_safety_recall | 100.0%, 100.0%, 100.0% | 100.0% | 0.0% | 100.0% to 100.0% | 0.0% | 0 of 135 |
| primary_intent | 77.2%, 77.2%, 77.2% | 77.2% | 0.0% | 77.2% to 77.2% | 0.0% | 0 of 135 |
| route | 73.3%, 74.1%, 75.6% | 74.3% | 1.1% | 73.3% to 75.6% | 2.8% | 4 of 135 |
