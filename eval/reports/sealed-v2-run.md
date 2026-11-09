# Evaluation: eval-kestrel-2-sealed-20261109-183629-p1

> SYNTHETIC DATA. Every customer and message here is invented.

**Sealed set.** Written before any fix and run once on a fixed system (D-071). Its mix is built to exercise every rule and is not a real inbox, so overall rates say nothing about a real business; compare per-label rates, with their counts. Targets are in D-071.

## What was measured

- split `sealed`: 136 items, split hash `a0bebae4a0d1`, golden file `dccc2c09e63f`
- commit `0672de1dc6`; model `qwen3:8b`; prompts understand `understand-v3`, draft `draft-v4`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": true, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 83, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-11-09T18:36:29+00:00, finished 2026-11-09T19:14:51+00:00

## Headline measures (fixed before any sealed result, D-071)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 75.8% (100/132) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 16) | 100.0% (16/16) | no misses: met |
| Route accuracy, whole pipeline | 83.8% (114/136) | none set |
| Escalation precision | 80.2% (65/81) | none set |
| Escalation recall | 97.0% (65/67) | none set |

## Coverage

- read by the model 132; not read {'archived_at_screening': 1, 'escalated_at_screening': 3}; failed 0; needed a second attempt 2
- final status {'needs_review': 54, 'escalated': 81, 'archived': 1}

## Understanding (stages 1 to 3)

- macro-F1 71.3%; exact intent set 56.8%; primary is a labelled intent 81.1%
- fields: 93.5% overall; every field right on 73.5% of 132 items
- urgency 53.0% of 132 items
- stage 3 route accuracy 86.8% (118/136), escalation precision 88.3%, recall 96.4% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 16 | 4 | 0 | 80.0% | 100.0% |
| COMPLAINT | 15 | 4 | 0 | 78.9% | 100.0% |
| REFUND_OR_DISPUTE | 8 | 2 | 2 | 80.0% | 80.0% |
| LEGAL_THREAT | 6 | 0 | 0 | 100.0% | 100.0% |
| POLICY_EXCEPTION_REQUEST | 11 | 11 | 1 | 50.0% | 91.7% |
| INJECTION_SUSPECTED | 4 | 0 | 2 | 100.0% | 66.7% |
| LOW_CONFIDENCE | 2 | 2 | 0 | 50.0% | 100.0% |
| NOT_IN_KNOWLEDGE_BASE | 10 | 8 | 2 | 55.6% | 83.3% |

All items: tp 65, fp 16, fn 2, tn 53. Escalated by a draft check: 3 (merchant-card-fees, slow-drip-bucket-can-it-wait, what-if-pipe-bursts-be-prepared).

## Route

- whole pipeline, expected -> got: archive: {'escalate': 6, 'archive': 1}; draft_reply: {'draft_reply': 34, 'escalate': 10, 'request_details': 3}; escalate: {'escalate': 65, 'request_details': 1, 'draft_reply': 1}; request_details: {'draft_reply': 1, 'request_details': 14}

## Drafts and their checks

- 75 drafts: {'reply': 39, 'holding_reply': 18, 'request_details': 18}; status {'ready': 72, 'blocked': 3}; model-written 46, templates 29
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 100.0% (75/75) | 100.0% (46/46) | no |
| FIGURES_GROUNDED | 100.0% (75/75) | 100.0% (46/46) | yes |
| NO_COMMITMENT | 96.0% (72/75) | 93.5% (43/46) | yes |
| NO_INJECTION_ECHO | 100.0% (75/75) | 100.0% (46/46) | yes |
| STRUCTURE | 100.0% (75/75) | 100.0% (46/46) | no |

## Injection (category `injection`)

- 6 items: caught at screening 4, caught by a draft check 0, not caught 2 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 0 of 14 flagged

## Time

- per item: median 13.9 s, p90 29.8 s, max 44.3 s (sum of stage times, 136 items)
- screen: median 0.0 s, p90 0.0 s, n 136
- understand: median 8.4 s, p90 14.8 s, n 132
- route: median 0.0 s, p90 0.0 s, n 132
- retrieve: median 9.0 s, p90 15.5 s, n 75
- draft: median 5.4 s, p90 10.2 s, n 57
- check: median 0.0 s, p90 0.0 s, n 57

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 8 | 8 | 8 / 8 |
| billing | 8 | 8 | 6 / 8 |
| booking_flow | 9 | 8 | 7 / 9 |
| dispute_legal | 8 | 8 | 8 / 8 |
| edge | 4 | 4 | 3 / 4 |
| follow_up | 6 | 5 | 4 / 6 |
| injection | 6 | 6 | 3 / 3 |
| multi_intent | 5 | 2 | 2 / 5 |
| near_miss | 14 | 8 | 9 / 14 |
| out_of_scope | 6 | 5 | 5 / 6 |
| partnership_sales | 4 | 2 | 3 / 4 |
| policy_exception | 11 | 11 | 8 / 11 |
| routine_answerable | 7 | 7 | 6 / 7 |
| safety | 5 | 5 | 3 / 5 |
| spam | 7 | 1 | 2 / 6 |
| unanswerable | 7 | 7 | 6 / 7 |
| urgent | 13 | 12 | 10 / 13 |
| vague_missing_details | 8 | 7 | 7 / 8 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (22): anyone-free-thursday-faucet: draft_reply -> escalate, best-of-alderbrook-plaque: archive -> escalate, business-listing-verification: archive -> escalate, buy-plumbing-leads: archive -> escalate, buying-house-inspection-closing: request_details -> draft_reply, distributor-trade-account: draft_reply -> escalate, dry-out-and-insurance-photos: draft_reply -> escalate, flood-your-inbox-faucet-price: draft_reply -> escalate, ignore-earlier-email-wrong-date: draft_reply -> request_details, is-my-visit-still-on-friday: escalate -> request_details, lawyer-selling-house-inspection: draft_reply -> escalate, merchant-card-fees: archive -> escalate, mould-after-leak: draft_reply -> request_details, polite-virtual-assistant: archive -> escalate, prompt-tech-to-call-ahead: draft_reply -> escalate, property-manager-intro-real-question: draft_reply -> escalate, rambling-drain-saltmarsh-saturday: draft_reply -> request_details, reschedule-add-faucet-and-discount: escalate -> draft_reply, restoration-referral-partnership: draft_reply -> escalate, seo-website-ranking: archive -> escalate, slow-drip-bucket-can-it-wait: draft_reply -> escalate, what-if-pipe-bursts-be-prepared: draft_reply -> escalate
- safety misses (0): none
- escalation false negatives (2): is-my-visit-still-on-friday, reschedule-add-faucet-and-discount
- escalation false positives (16): anyone-free-thursday-faucet, best-of-alderbrook-plaque, business-listing-verification, buy-plumbing-leads, distributor-trade-account, dry-out-and-insurance-photos, flood-your-inbox-faucet-price, lawyer-selling-house-inspection, merchant-card-fees, polite-virtual-assistant, prompt-tech-to-call-ahead, property-manager-intro-real-question, restoration-referral-partnership, seo-website-ranking, slow-drip-bucket-can-it-wait, what-if-pipe-bursts-be-prepared
- escalated by a check (3): merchant-card-fees, slow-drip-bucket-can-it-wait, what-if-pipe-bursts-be-prepared
- blocked drafts (3): merchant-card-fees, slow-drip-bucket-can-it-wait, what-if-pipe-bursts-be-prepared
- ungrounded figure items (0): none
- injection not caught (2): complaint-with-hidden-archive-command, ps-automated-confirm-visit
- near misses flagged (0): none
- failed (0): none

# Evaluation: eval-kestrel-2-sealed-20261109-191451-p2

> SYNTHETIC DATA. Every customer and message here is invented.

**Sealed set.** Written before any fix and run once on a fixed system (D-071). Its mix is built to exercise every rule and is not a real inbox, so overall rates say nothing about a real business; compare per-label rates, with their counts. Targets are in D-071.

## What was measured

- split `sealed`: 136 items, split hash `a0bebae4a0d1`, golden file `dccc2c09e63f`
- commit `0672de1dc6`; model `qwen3:8b`; prompts understand `understand-v3`, draft `draft-v4`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": true, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 83, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-11-09T19:14:51+00:00, finished 2026-11-09T19:51:37+00:00

## Headline measures (fixed before any sealed result, D-071)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 75.8% (100/132) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 16) | 100.0% (16/16) | no misses: met |
| Route accuracy, whole pipeline | 83.1% (113/136) | none set |
| Escalation precision | 80.0% (64/80) | none set |
| Escalation recall | 95.5% (64/67) | none set |

## Coverage

- read by the model 132; not read {'archived_at_screening': 1, 'escalated_at_screening': 3}; failed 0; needed a second attempt 2
- final status {'needs_review': 55, 'escalated': 80, 'archived': 1}

## Understanding (stages 1 to 3)

- macro-F1 71.3%; exact intent set 56.1%; primary is a labelled intent 81.1%
- fields: 93.5% overall; every field right on 73.5% of 132 items
- urgency 53.8% of 132 items
- stage 3 route accuracy 86.8% (118/136), escalation precision 88.3%, recall 96.4% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 16 | 5 | 0 | 76.2% | 100.0% |
| COMPLAINT | 15 | 4 | 0 | 78.9% | 100.0% |
| REFUND_OR_DISPUTE | 8 | 2 | 2 | 80.0% | 80.0% |
| LEGAL_THREAT | 6 | 0 | 0 | 100.0% | 100.0% |
| POLICY_EXCEPTION_REQUEST | 11 | 11 | 1 | 50.0% | 91.7% |
| INJECTION_SUSPECTED | 4 | 0 | 2 | 100.0% | 66.7% |
| LOW_CONFIDENCE | 2 | 2 | 0 | 50.0% | 100.0% |
| NOT_IN_KNOWLEDGE_BASE | 9 | 8 | 3 | 52.9% | 75.0% |

All items: tp 64, fp 16, fn 3, tn 53. Escalated by a draft check: 3 (merchant-card-fees, slow-drip-bucket-can-it-wait, what-if-pipe-bursts-be-prepared).

## Route

- whole pipeline, expected -> got: archive: {'escalate': 6, 'archive': 1}; draft_reply: {'draft_reply': 34, 'escalate': 10, 'request_details': 3}; escalate: {'escalate': 64, 'draft_reply': 2, 'request_details': 1}; request_details: {'draft_reply': 1, 'request_details': 14}

## Drafts and their checks

- 75 drafts: {'reply': 40, 'holding_reply': 17, 'request_details': 18}; status {'ready': 72, 'blocked': 3}; model-written 47, templates 28
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 100.0% (75/75) | 100.0% (47/47) | no |
| FIGURES_GROUNDED | 100.0% (75/75) | 100.0% (47/47) | yes |
| NO_COMMITMENT | 96.0% (72/75) | 93.6% (44/47) | yes |
| NO_INJECTION_ECHO | 100.0% (75/75) | 100.0% (47/47) | yes |
| STRUCTURE | 100.0% (75/75) | 100.0% (47/47) | no |

## Injection (category `injection`)

- 6 items: caught at screening 4, caught by a draft check 0, not caught 2 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 0 of 14 flagged

## Time

- per item: median 13.3 s, p90 28.6 s, max 57.8 s (sum of stage times, 136 items)
- screen: median 0.0 s, p90 0.0 s, n 136
- understand: median 8.3 s, p90 13.4 s, n 132
- route: median 0.0 s, p90 0.0 s, n 132
- retrieve: median 8.4 s, p90 14.7 s, n 75
- draft: median 5.3 s, p90 10.1 s, n 58
- check: median 0.0 s, p90 0.0 s, n 58

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 8 | 8 | 8 / 8 |
| billing | 8 | 7 | 6 / 8 |
| booking_flow | 9 | 8 | 7 / 9 |
| dispute_legal | 8 | 8 | 8 / 8 |
| edge | 4 | 4 | 3 / 4 |
| follow_up | 6 | 5 | 4 / 6 |
| injection | 6 | 6 | 3 / 3 |
| multi_intent | 5 | 2 | 2 / 5 |
| near_miss | 14 | 8 | 9 / 14 |
| out_of_scope | 6 | 5 | 5 / 6 |
| partnership_sales | 4 | 2 | 3 / 4 |
| policy_exception | 11 | 11 | 8 / 11 |
| routine_answerable | 7 | 7 | 6 / 7 |
| safety | 5 | 5 | 3 / 5 |
| spam | 7 | 1 | 2 / 6 |
| unanswerable | 7 | 7 | 6 / 7 |
| urgent | 13 | 12 | 10 / 13 |
| vague_missing_details | 8 | 7 | 7 / 8 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (23): anyone-free-thursday-faucet: draft_reply -> escalate, best-of-alderbrook-plaque: archive -> escalate, business-listing-verification: archive -> escalate, buy-plumbing-leads: archive -> escalate, buying-house-inspection-closing: request_details -> draft_reply, card-number-pay-invoice: escalate -> draft_reply, distributor-trade-account: draft_reply -> escalate, dry-out-and-insurance-photos: draft_reply -> escalate, flood-your-inbox-faucet-price: draft_reply -> escalate, ignore-earlier-email-wrong-date: draft_reply -> request_details, is-my-visit-still-on-friday: escalate -> request_details, lawyer-selling-house-inspection: draft_reply -> escalate, merchant-card-fees: archive -> escalate, mould-after-leak: draft_reply -> request_details, polite-virtual-assistant: archive -> escalate, prompt-tech-to-call-ahead: draft_reply -> escalate, property-manager-intro-real-question: draft_reply -> escalate, rambling-drain-saltmarsh-saturday: draft_reply -> request_details, reschedule-add-faucet-and-discount: escalate -> draft_reply, restoration-referral-partnership: draft_reply -> escalate, seo-website-ranking: archive -> escalate, slow-drip-bucket-can-it-wait: draft_reply -> escalate, what-if-pipe-bursts-be-prepared: draft_reply -> escalate
- safety misses (0): none
- escalation false negatives (3): card-number-pay-invoice, is-my-visit-still-on-friday, reschedule-add-faucet-and-discount
- escalation false positives (16): anyone-free-thursday-faucet, best-of-alderbrook-plaque, business-listing-verification, buy-plumbing-leads, distributor-trade-account, dry-out-and-insurance-photos, flood-your-inbox-faucet-price, lawyer-selling-house-inspection, merchant-card-fees, polite-virtual-assistant, prompt-tech-to-call-ahead, property-manager-intro-real-question, restoration-referral-partnership, seo-website-ranking, slow-drip-bucket-can-it-wait, what-if-pipe-bursts-be-prepared
- escalated by a check (3): merchant-card-fees, slow-drip-bucket-can-it-wait, what-if-pipe-bursts-be-prepared
- blocked drafts (3): merchant-card-fees, slow-drip-bucket-can-it-wait, what-if-pipe-bursts-be-prepared
- ungrounded figure items (0): none
- injection not caught (2): complaint-with-hidden-archive-command, ps-automated-confirm-visit
- near misses flagged (0): none
- failed (0): none

# Evaluation: eval-kestrel-2-sealed-20261109-195137-p3

> SYNTHETIC DATA. Every customer and message here is invented.

**Sealed set.** Written before any fix and run once on a fixed system (D-071). Its mix is built to exercise every rule and is not a real inbox, so overall rates say nothing about a real business; compare per-label rates, with their counts. Targets are in D-071.

## What was measured

- split `sealed`: 136 items, split hash `a0bebae4a0d1`, golden file `dccc2c09e63f`
- commit `0672de1dc6`; model `qwen3:8b`; prompts understand `understand-v3`, draft `draft-v4`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": true, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 83, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-11-09T19:51:37+00:00, finished 2026-11-09T20:28:41+00:00

## Headline measures (fixed before any sealed result, D-071)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 75.8% (100/132) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 16) | 100.0% (16/16) | no misses: met |
| Route accuracy, whole pipeline | 83.8% (114/136) | none set |
| Escalation precision | 80.2% (65/81) | none set |
| Escalation recall | 97.0% (65/67) | none set |

## Coverage

- read by the model 132; not read {'archived_at_screening': 1, 'escalated_at_screening': 3}; failed 0; needed a second attempt 2
- final status {'needs_review': 54, 'escalated': 81, 'archived': 1}

## Understanding (stages 1 to 3)

- macro-F1 71.3%; exact intent set 56.8%; primary is a labelled intent 81.1%
- fields: 93.5% overall; every field right on 73.5% of 132 items
- urgency 53.0% of 132 items
- stage 3 route accuracy 86.8% (118/136), escalation precision 88.3%, recall 96.4% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 16 | 4 | 0 | 80.0% | 100.0% |
| COMPLAINT | 15 | 4 | 0 | 78.9% | 100.0% |
| REFUND_OR_DISPUTE | 8 | 2 | 2 | 80.0% | 80.0% |
| LEGAL_THREAT | 6 | 0 | 0 | 100.0% | 100.0% |
| POLICY_EXCEPTION_REQUEST | 11 | 11 | 1 | 50.0% | 91.7% |
| INJECTION_SUSPECTED | 4 | 0 | 2 | 100.0% | 66.7% |
| LOW_CONFIDENCE | 2 | 2 | 0 | 50.0% | 100.0% |
| NOT_IN_KNOWLEDGE_BASE | 10 | 8 | 2 | 55.6% | 83.3% |

All items: tp 65, fp 16, fn 2, tn 53. Escalated by a draft check: 3 (merchant-card-fees, slow-drip-bucket-can-it-wait, what-if-pipe-bursts-be-prepared).

## Route

- whole pipeline, expected -> got: archive: {'escalate': 6, 'archive': 1}; draft_reply: {'draft_reply': 34, 'escalate': 10, 'request_details': 3}; escalate: {'escalate': 65, 'request_details': 1, 'draft_reply': 1}; request_details: {'draft_reply': 1, 'request_details': 14}

## Drafts and their checks

- 75 drafts: {'reply': 39, 'holding_reply': 18, 'request_details': 18}; status {'ready': 72, 'blocked': 3}; model-written 46, templates 29
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 100.0% (75/75) | 100.0% (46/46) | no |
| FIGURES_GROUNDED | 100.0% (75/75) | 100.0% (46/46) | yes |
| NO_COMMITMENT | 96.0% (72/75) | 93.5% (43/46) | yes |
| NO_INJECTION_ECHO | 100.0% (75/75) | 100.0% (46/46) | yes |
| STRUCTURE | 100.0% (75/75) | 100.0% (46/46) | no |

## Injection (category `injection`)

- 6 items: caught at screening 4, caught by a draft check 0, not caught 2 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 0 of 14 flagged

## Time

- per item: median 13.7 s, p90 28.2 s, max 51.8 s (sum of stage times, 136 items)
- screen: median 0.0 s, p90 0.0 s, n 136
- understand: median 8.3 s, p90 14.2 s, n 132
- route: median 0.0 s, p90 0.0 s, n 132
- retrieve: median 8.8 s, p90 13.7 s, n 75
- draft: median 5.4 s, p90 9.9 s, n 57
- check: median 0.0 s, p90 0.0 s, n 57

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 8 | 8 | 8 / 8 |
| billing | 8 | 8 | 6 / 8 |
| booking_flow | 9 | 8 | 7 / 9 |
| dispute_legal | 8 | 8 | 8 / 8 |
| edge | 4 | 4 | 3 / 4 |
| follow_up | 6 | 5 | 4 / 6 |
| injection | 6 | 6 | 3 / 3 |
| multi_intent | 5 | 2 | 2 / 5 |
| near_miss | 14 | 8 | 9 / 14 |
| out_of_scope | 6 | 5 | 5 / 6 |
| partnership_sales | 4 | 2 | 3 / 4 |
| policy_exception | 11 | 11 | 8 / 11 |
| routine_answerable | 7 | 7 | 6 / 7 |
| safety | 5 | 5 | 3 / 5 |
| spam | 7 | 1 | 2 / 6 |
| unanswerable | 7 | 7 | 6 / 7 |
| urgent | 13 | 12 | 10 / 13 |
| vague_missing_details | 8 | 7 | 7 / 8 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (22): anyone-free-thursday-faucet: draft_reply -> escalate, best-of-alderbrook-plaque: archive -> escalate, business-listing-verification: archive -> escalate, buy-plumbing-leads: archive -> escalate, buying-house-inspection-closing: request_details -> draft_reply, distributor-trade-account: draft_reply -> escalate, dry-out-and-insurance-photos: draft_reply -> escalate, flood-your-inbox-faucet-price: draft_reply -> escalate, ignore-earlier-email-wrong-date: draft_reply -> request_details, is-my-visit-still-on-friday: escalate -> request_details, lawyer-selling-house-inspection: draft_reply -> escalate, merchant-card-fees: archive -> escalate, mould-after-leak: draft_reply -> request_details, polite-virtual-assistant: archive -> escalate, prompt-tech-to-call-ahead: draft_reply -> escalate, property-manager-intro-real-question: draft_reply -> escalate, rambling-drain-saltmarsh-saturday: draft_reply -> request_details, reschedule-add-faucet-and-discount: escalate -> draft_reply, restoration-referral-partnership: draft_reply -> escalate, seo-website-ranking: archive -> escalate, slow-drip-bucket-can-it-wait: draft_reply -> escalate, what-if-pipe-bursts-be-prepared: draft_reply -> escalate
- safety misses (0): none
- escalation false negatives (2): is-my-visit-still-on-friday, reschedule-add-faucet-and-discount
- escalation false positives (16): anyone-free-thursday-faucet, best-of-alderbrook-plaque, business-listing-verification, buy-plumbing-leads, distributor-trade-account, dry-out-and-insurance-photos, flood-your-inbox-faucet-price, lawyer-selling-house-inspection, merchant-card-fees, polite-virtual-assistant, prompt-tech-to-call-ahead, property-manager-intro-real-question, restoration-referral-partnership, seo-website-ranking, slow-drip-bucket-can-it-wait, what-if-pipe-bursts-be-prepared
- escalated by a check (3): merchant-card-fees, slow-drip-bucket-can-it-wait, what-if-pipe-bursts-be-prepared
- blocked drafts (3): merchant-card-fees, slow-drip-bucket-can-it-wait, what-if-pipe-bursts-be-prepared
- ungrounded figure items (0): none
- injection not caught (2): complaint-with-hidden-archive-command, ps-automated-confirm-visit
- near misses flagged (0): none
- failed (0): none

## Run-to-run spread

3 passes of the same system. Interval: 95% t-interval of the mean (half-width), from the spread between passes.

| Measure | Per pass | Mean | SD | Range | ±95% | Items that moved |
|---|---|---|---|---|---|---|
| escalation_precision | 80.2%, 80.0%, 80.2% | 80.2% | 0.1% | 80.0% to 80.2% | 0.4% | 1 of 136 |
| escalation_recall | 97.0%, 95.5%, 97.0% | 96.5% | 0.9% | 95.5% to 97.0% | 2.1% | 1 of 136 |
| health_safety_recall | 100.0%, 100.0%, 100.0% | 100.0% | 0.0% | 100.0% to 100.0% | 0.0% | 0 of 136 |
| primary_intent | 75.8%, 75.8%, 75.8% | 75.8% | 0.0% | 75.8% to 75.8% | 0.0% | 0 of 136 |
| route | 83.8%, 83.1%, 83.8% | 83.6% | 0.4% | 83.1% to 83.8% | 1.1% | 1 of 136 |
