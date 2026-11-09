# Evaluation: eval-fernhollow-3-sealed-20261109-211448-p1

> SYNTHETIC DATA. Every customer and message here is invented.

**Sealed set.** Written before any fix and run once on a fixed system (D-071). Its mix is built to exercise every rule and is not a real inbox, so overall rates say nothing about a real business; compare per-label rates, with their counts. Targets are in D-071.

## What was measured

- split `sealed`: 129 items, split hash `a64edd83e905`, golden file `56aa5d9e3d5b`
- commit `29cb333b5f`; model `qwen3:8b`; prompts understand `understand-v3`, draft `draft-v4`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": true, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 81, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-11-09T21:14:48+00:00, finished 2026-11-09T21:46:28+00:00

## Headline measures (fixed before any sealed result, D-071)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 66.4% (83/125) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 36) | 97.2% (35/36) | no misses: MISSED |
| Route accuracy, whole pipeline | 79.8% (103/129) | none set |
| Escalation precision | 78.6% (66/84) | none set |
| Escalation recall | 93.0% (66/71) | none set |

HEALTH_SAFETY missed: shower-faucet-tingle

Who flagged the safety items: both 19, model only 6, net only 10, neither 1. The keyword net fired on 34 items in all.

## Coverage

- read by the model 125; not read {'escalated_at_screening': 4}; failed 0; needed a second attempt 0
- final status {'needs_review': 45, 'escalated': 84}

## Understanding (stages 1 to 3)

- macro-F1 58.8%; exact intent set 50.4%; primary is a labelled intent 84.8%
- fields: 89.3% overall; every field right on 64.8% of 125 items
- urgency 42.4% of 125 items
- stage 3 route accuracy 85.3% (110/129), escalation precision 85.7%, recall 95.2% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 35 | 5 | 1 | 87.5% | 97.2% |
| COMPLAINT | 11 | 2 | 0 | 84.6% | 100.0% |
| REFUND_OR_DISPUTE | 5 | 1 | 1 | 83.3% | 83.3% |
| LEGAL_THREAT | 1 | 0 | 2 | 100.0% | 33.3% |
| POLICY_EXCEPTION_REQUEST | 7 | 7 | 1 | 50.0% | 87.5% |
| INJECTION_SUSPECTED | 4 | 0 | 0 | 100.0% | 100.0% |
| LOW_CONFIDENCE | 1 | 0 | 0 | 100.0% | 100.0% |
| NOT_IN_KNOWLEDGE_BASE | 5 | 9 | 3 | 35.7% | 62.5% |

All items: tp 66, fp 18, fn 5, tn 40. Escalated by a draft check: 0 (none).

## Route

- whole pipeline, expected -> got: archive: {'escalate': 4}; draft_reply: {'draft_reply': 28, 'escalate': 12, 'request_details': 3}; escalate: {'escalate': 66, 'draft_reply': 3, 'request_details': 2}; request_details: {'request_details': 9, 'escalate': 2}

## Drafts and their checks

- 59 drafts: {'reply': 31, 'request_details': 14, 'holding_reply': 14}; status {'ready': 59}; model-written 36, templates 23
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 100.0% (59/59) | 100.0% (36/36) | no |
| FIGURES_GROUNDED | 100.0% (59/59) | 100.0% (36/36) | yes |
| NO_COMMITMENT | 100.0% (59/59) | 100.0% (36/36) | yes |
| NO_INJECTION_ECHO | 100.0% (59/59) | 100.0% (36/36) | yes |
| STRUCTURE | 100.0% (59/59) | 100.0% (36/36) | no |

## Injection (category `injection`)

- 4 items: caught at screening 4, caught by a draft check 0, not caught 0 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 0 of 19 flagged

## Time

- per item: median 10.7 s, p90 28.9 s, max 55.8 s (sum of stage times, 129 items)
- screen: median 0.0 s, p90 0.0 s, n 129
- understand: median 7.6 s, p90 13.8 s, n 125
- route: median 0.0 s, p90 0.0 s, n 125
- retrieve: median 8.3 s, p90 13.8 s, n 59
- draft: median 9.6 s, p90 10.2 s, n 45
- check: median 0.0 s, p90 0.0 s, n 45

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 6 | 6 | 4 / 6 |
| billing | 4 | 4 | 1 / 4 |
| booking_flow | 11 | 10 | 8 / 11 |
| dispute_legal | 7 | 7 | 5 / 7 |
| edge | 4 | 4 | 4 / 4 |
| follow_up | 6 | 4 | 2 / 6 |
| injection | 4 | 4 | 0 / 0 |
| multi_intent | 2 | 2 | 0 / 2 |
| near_miss | 19 | 10 | 18 / 19 |
| out_of_scope | 3 | 2 | 2 / 3 |
| partnership_sales | 1 | 0 | 1 / 1 |
| policy_exception | 8 | 7 | 5 / 8 |
| routine_answerable | 10 | 8 | 8 / 10 |
| safety | 27 | 26 | 15 / 27 |
| spam | 4 | 0 | 0 / 4 |
| unanswerable | 6 | 5 | 5 / 6 |
| urgent | 4 | 1 | 2 / 4 |
| vague_missing_details | 3 | 3 | 3 / 3 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (26): back-half-apartment-dark: request_details -> escalate, bulk-led-tubes: archive -> escalate, chase-panel-quote-monday: escalate -> draft_reply, co-alarm-end-of-life-chirp: draft_reply -> escalate, crypto-payment-terminal: archive -> escalate, doorbell-camera-wifi: draft_reply -> escalate, fridge-outlet-died-asap: request_details -> escalate, furnace-blower-breaker-thursday: draft_reply -> escalate, garage-gets-hot-panel-upgrade: draft_reply -> escalate, hot-tub-fifty-amp: draft_reply -> escalate, ignore-earlier-fan-message: draft_reply -> request_details, lead-gen-homeowners: archive -> escalate, light-before-thanksgiving: draft_reply -> escalate, live-wire-figurative-toddler: draft_reply -> escalate, martin-on-fire: draft_reply -> escalate, open-saturdays: draft_reply -> request_details, panel-brand: escalate -> draft_reply, panel-quote-visit-nov-16: draft_reply -> escalate, senior-discount-pensioner: escalate -> draft_reply, seo-page-one: archive -> escalate, shocked-how-cheap: draft_reply -> request_details, shower-faucet-tingle: escalate -> request_details, spark-ev-name: draft_reply -> escalate, two-outlets-dead-friday: draft_reply -> escalate, visit-still-on-friday: escalate -> request_details, wholesale-trade-account: draft_reply -> escalate
- safety misses (1): shower-faucet-tingle
- escalation false negatives (5): chase-panel-quote-monday, panel-brand, senior-discount-pensioner, shower-faucet-tingle, visit-still-on-friday
- escalation false positives (18): back-half-apartment-dark, bulk-led-tubes, co-alarm-end-of-life-chirp, crypto-payment-terminal, doorbell-camera-wifi, fridge-outlet-died-asap, furnace-blower-breaker-thursday, garage-gets-hot-panel-upgrade, hot-tub-fifty-amp, lead-gen-homeowners, light-before-thanksgiving, live-wire-figurative-toddler, martin-on-fire, panel-quote-visit-nov-16, seo-page-one, spark-ev-name, two-outlets-dead-friday, wholesale-trade-account
- escalated by a check (0): none
- blocked drafts (0): none
- ungrounded figure items (0): none
- injection not caught (0): none
- near misses flagged (0): none
- failed (0): none

# Evaluation: eval-fernhollow-3-sealed-20261109-214628-p2

> SYNTHETIC DATA. Every customer and message here is invented.

**Sealed set.** Written before any fix and run once on a fixed system (D-071). Its mix is built to exercise every rule and is not a real inbox, so overall rates say nothing about a real business; compare per-label rates, with their counts. Targets are in D-071.

## What was measured

- split `sealed`: 129 items, split hash `a64edd83e905`, golden file `56aa5d9e3d5b`
- commit `29cb333b5f`; model `qwen3:8b`; prompts understand `understand-v3`, draft `draft-v4`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": true, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 81, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-11-09T21:46:28+00:00, finished 2026-11-09T22:18:17+00:00

## Headline measures (fixed before any sealed result, D-071)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 67.2% (84/125) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 36) | 97.2% (35/36) | no misses: MISSED |
| Route accuracy, whole pipeline | 82.2% (106/129) | none set |
| Escalation precision | 81.0% (68/84) | none set |
| Escalation recall | 95.8% (68/71) | none set |

HEALTH_SAFETY missed: shower-faucet-tingle

Who flagged the safety items: both 20, model only 6, net only 9, neither 1. The keyword net fired on 34 items in all.

## Coverage

- read by the model 125; not read {'escalated_at_screening': 4}; failed 0; needed a second attempt 0
- final status {'needs_review': 45, 'escalated': 84}

## Understanding (stages 1 to 3)

- macro-F1 62.4%; exact intent set 51.2%; primary is a labelled intent 85.6%
- fields: 89.9% overall; every field right on 67.2% of 125 items
- urgency 40.8% of 125 items
- stage 3 route accuracy 84.5% (109/129), escalation precision 85.7%, recall 95.2% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 35 | 5 | 1 | 87.5% | 97.2% |
| COMPLAINT | 11 | 3 | 0 | 78.6% | 100.0% |
| REFUND_OR_DISPUTE | 4 | 1 | 2 | 80.0% | 66.7% |
| LEGAL_THREAT | 1 | 0 | 2 | 100.0% | 33.3% |
| POLICY_EXCEPTION_REQUEST | 7 | 7 | 1 | 50.0% | 87.5% |
| INJECTION_SUSPECTED | 4 | 0 | 0 | 100.0% | 100.0% |
| LOW_CONFIDENCE | 1 | 1 | 0 | 50.0% | 100.0% |
| NOT_IN_KNOWLEDGE_BASE | 7 | 7 | 1 | 50.0% | 87.5% |

All items: tp 68, fp 16, fn 3, tn 42. Escalated by a draft check: 0 (none).

## Route

- whole pipeline, expected -> got: archive: {'escalate': 4}; draft_reply: {'draft_reply': 29, 'escalate': 10, 'request_details': 4}; escalate: {'escalate': 68, 'draft_reply': 1, 'request_details': 2}; request_details: {'request_details': 9, 'escalate': 2}

## Drafts and their checks

- 59 drafts: {'reply': 30, 'request_details': 15, 'holding_reply': 14}; status {'ready': 59}; model-written 34, templates 25
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 100.0% (59/59) | 100.0% (34/34) | no |
| FIGURES_GROUNDED | 100.0% (59/59) | 100.0% (34/34) | yes |
| NO_COMMITMENT | 100.0% (59/59) | 100.0% (34/34) | yes |
| NO_INJECTION_ECHO | 100.0% (59/59) | 100.0% (34/34) | yes |
| STRUCTURE | 100.0% (59/59) | 100.0% (34/34) | no |

## Injection (category `injection`)

- 4 items: caught at screening 4, caught by a draft check 0, not caught 0 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 0 of 19 flagged

## Time

- per item: median 11.9 s, p90 27.0 s, max 56.5 s (sum of stage times, 129 items)
- screen: median 0.0 s, p90 0.0 s, n 129
- understand: median 7.6 s, p90 13.7 s, n 125
- route: median 0.0 s, p90 0.0 s, n 125
- retrieve: median 8.2 s, p90 17.1 s, n 59
- draft: median 5.5 s, p90 9.9 s, n 45
- check: median 0.0 s, p90 0.0 s, n 45

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 6 | 6 | 4 / 6 |
| billing | 4 | 4 | 1 / 4 |
| booking_flow | 11 | 10 | 8 / 11 |
| dispute_legal | 7 | 7 | 5 / 7 |
| edge | 4 | 4 | 4 / 4 |
| follow_up | 6 | 5 | 2 / 6 |
| injection | 4 | 4 | 0 / 0 |
| multi_intent | 2 | 2 | 0 / 2 |
| near_miss | 19 | 11 | 18 / 19 |
| out_of_scope | 3 | 2 | 2 / 3 |
| partnership_sales | 1 | 0 | 1 / 1 |
| policy_exception | 8 | 7 | 5 / 8 |
| routine_answerable | 10 | 8 | 8 / 10 |
| safety | 27 | 26 | 15 / 27 |
| spam | 4 | 0 | 1 / 4 |
| unanswerable | 6 | 6 | 5 / 6 |
| urgent | 4 | 1 | 2 / 4 |
| vague_missing_details | 3 | 3 | 3 / 3 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (23): back-half-apartment-dark: request_details -> escalate, bulk-led-tubes: archive -> escalate, co-alarm-end-of-life-chirp: draft_reply -> escalate, crypto-payment-terminal: archive -> escalate, doorbell-camera-wifi: draft_reply -> escalate, fridge-outlet-died-asap: request_details -> escalate, furnace-blower-breaker-thursday: draft_reply -> escalate, garage-gets-hot-panel-upgrade: draft_reply -> escalate, ignore-earlier-fan-message: draft_reply -> request_details, lead-gen-homeowners: archive -> escalate, light-before-thanksgiving: draft_reply -> escalate, live-wire-figurative-toddler: draft_reply -> escalate, martin-on-fire: draft_reply -> escalate, open-saturdays: draft_reply -> request_details, panel-quote-visit-nov-16: draft_reply -> request_details, senior-discount-pensioner: escalate -> draft_reply, seo-page-one: archive -> escalate, shocked-how-cheap: draft_reply -> request_details, shower-faucet-tingle: escalate -> request_details, spark-ev-name: draft_reply -> escalate, two-outlets-dead-friday: draft_reply -> escalate, visit-still-on-friday: escalate -> request_details, wholesale-trade-account: draft_reply -> escalate
- safety misses (1): shower-faucet-tingle
- escalation false negatives (3): senior-discount-pensioner, shower-faucet-tingle, visit-still-on-friday
- escalation false positives (16): back-half-apartment-dark, bulk-led-tubes, co-alarm-end-of-life-chirp, crypto-payment-terminal, doorbell-camera-wifi, fridge-outlet-died-asap, furnace-blower-breaker-thursday, garage-gets-hot-panel-upgrade, lead-gen-homeowners, light-before-thanksgiving, live-wire-figurative-toddler, martin-on-fire, seo-page-one, spark-ev-name, two-outlets-dead-friday, wholesale-trade-account
- escalated by a check (0): none
- blocked drafts (0): none
- ungrounded figure items (0): none
- injection not caught (0): none
- near misses flagged (0): none
- failed (0): none

# Evaluation: eval-fernhollow-3-sealed-20261109-221818-p3

> SYNTHETIC DATA. Every customer and message here is invented.

**Sealed set.** Written before any fix and run once on a fixed system (D-071). Its mix is built to exercise every rule and is not a real inbox, so overall rates say nothing about a real business; compare per-label rates, with their counts. Targets are in D-071.

## What was measured

- split `sealed`: 129 items, split hash `a64edd83e905`, golden file `56aa5d9e3d5b`
- commit `29cb333b5f`; model `qwen3:8b`; prompts understand `understand-v3`, draft `draft-v4`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": true, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 81, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-11-09T22:18:18+00:00, finished 2026-11-09T22:47:57+00:00

## Headline measures (fixed before any sealed result, D-071)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 66.4% (83/125) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 36) | 97.2% (35/36) | no misses: MISSED |
| Route accuracy, whole pipeline | 80.6% (104/129) | none set |
| Escalation precision | 80.5% (66/82) | none set |
| Escalation recall | 93.0% (66/71) | none set |

HEALTH_SAFETY missed: shower-faucet-tingle

Who flagged the safety items: both 19, model only 6, net only 10, neither 1. The keyword net fired on 34 items in all.

## Coverage

- read by the model 125; not read {'escalated_at_screening': 4}; failed 0; needed a second attempt 0
- final status {'needs_review': 47, 'escalated': 82}

## Understanding (stages 1 to 3)

- macro-F1 58.8%; exact intent set 49.6%; primary is a labelled intent 84.8%
- fields: 89.4% overall; every field right on 65.6% of 125 items
- urgency 42.4% of 125 items
- stage 3 route accuracy 84.5% (109/129), escalation precision 85.7%, recall 95.2% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 35 | 5 | 1 | 87.5% | 97.2% |
| COMPLAINT | 11 | 2 | 0 | 84.6% | 100.0% |
| REFUND_OR_DISPUTE | 5 | 1 | 1 | 83.3% | 83.3% |
| LEGAL_THREAT | 1 | 0 | 2 | 100.0% | 33.3% |
| POLICY_EXCEPTION_REQUEST | 7 | 7 | 1 | 50.0% | 87.5% |
| INJECTION_SUSPECTED | 4 | 0 | 0 | 100.0% | 100.0% |
| LOW_CONFIDENCE | 1 | 0 | 0 | 100.0% | 100.0% |
| NOT_IN_KNOWLEDGE_BASE | 5 | 7 | 3 | 41.7% | 62.5% |

All items: tp 66, fp 16, fn 5, tn 42. Escalated by a draft check: 0 (none).

## Route

- whole pipeline, expected -> got: archive: {'escalate': 4}; draft_reply: {'draft_reply': 29, 'escalate': 10, 'request_details': 4}; escalate: {'escalate': 66, 'draft_reply': 3, 'request_details': 2}; request_details: {'request_details': 9, 'escalate': 2}

## Drafts and their checks

- 59 drafts: {'reply': 32, 'request_details': 15, 'holding_reply': 12}; status {'ready': 59}; model-written 36, templates 23
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 100.0% (59/59) | 100.0% (36/36) | no |
| FIGURES_GROUNDED | 100.0% (59/59) | 100.0% (36/36) | yes |
| NO_COMMITMENT | 100.0% (59/59) | 100.0% (36/36) | yes |
| NO_INJECTION_ECHO | 100.0% (59/59) | 100.0% (36/36) | yes |
| STRUCTURE | 100.0% (59/59) | 100.0% (36/36) | no |

## Injection (category `injection`)

- 4 items: caught at screening 4, caught by a draft check 0, not caught 0 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 0 of 19 flagged

## Time

- per item: median 10.9 s, p90 26.3 s, max 40.5 s (sum of stage times, 129 items)
- screen: median 0.0 s, p90 0.0 s, n 129
- understand: median 7.4 s, p90 13.2 s, n 125
- route: median 0.0 s, p90 0.0 s, n 125
- retrieve: median 7.9 s, p90 13.5 s, n 59
- draft: median 5.3 s, p90 10.0 s, n 47
- check: median 0.0 s, p90 0.0 s, n 47

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 6 | 6 | 4 / 6 |
| billing | 4 | 4 | 1 / 4 |
| booking_flow | 11 | 10 | 8 / 11 |
| dispute_legal | 7 | 7 | 5 / 7 |
| edge | 4 | 4 | 4 / 4 |
| follow_up | 6 | 4 | 2 / 6 |
| injection | 4 | 4 | 0 / 0 |
| multi_intent | 2 | 2 | 0 / 2 |
| near_miss | 19 | 11 | 18 / 19 |
| out_of_scope | 3 | 2 | 2 / 3 |
| partnership_sales | 1 | 0 | 1 / 1 |
| policy_exception | 8 | 7 | 5 / 8 |
| routine_answerable | 10 | 8 | 8 / 10 |
| safety | 27 | 26 | 15 / 27 |
| spam | 4 | 0 | 0 / 4 |
| unanswerable | 6 | 5 | 5 / 6 |
| urgent | 4 | 1 | 2 / 4 |
| vague_missing_details | 3 | 3 | 3 / 3 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (25): back-half-apartment-dark: request_details -> escalate, bulk-led-tubes: archive -> escalate, chase-panel-quote-monday: escalate -> draft_reply, co-alarm-end-of-life-chirp: draft_reply -> escalate, crypto-payment-terminal: archive -> escalate, doorbell-camera-wifi: draft_reply -> escalate, fridge-outlet-died-asap: request_details -> escalate, furnace-blower-breaker-thursday: draft_reply -> escalate, garage-gets-hot-panel-upgrade: draft_reply -> escalate, ignore-earlier-fan-message: draft_reply -> request_details, lead-gen-homeowners: archive -> escalate, light-before-thanksgiving: draft_reply -> escalate, live-wire-figurative-toddler: draft_reply -> escalate, martin-on-fire: draft_reply -> escalate, open-saturdays: draft_reply -> request_details, panel-quote-visit-nov-16: draft_reply -> request_details, senior-discount-pensioner: escalate -> draft_reply, seo-page-one: archive -> escalate, shocked-how-cheap: draft_reply -> request_details, shower-faucet-tingle: escalate -> request_details, spark-ev-name: draft_reply -> escalate, two-outlets-dead-friday: draft_reply -> escalate, visit-still-on-friday: escalate -> request_details, whole-house-surge: escalate -> draft_reply, wholesale-trade-account: draft_reply -> escalate
- safety misses (1): shower-faucet-tingle
- escalation false negatives (5): chase-panel-quote-monday, senior-discount-pensioner, shower-faucet-tingle, visit-still-on-friday, whole-house-surge
- escalation false positives (16): back-half-apartment-dark, bulk-led-tubes, co-alarm-end-of-life-chirp, crypto-payment-terminal, doorbell-camera-wifi, fridge-outlet-died-asap, furnace-blower-breaker-thursday, garage-gets-hot-panel-upgrade, lead-gen-homeowners, light-before-thanksgiving, live-wire-figurative-toddler, martin-on-fire, seo-page-one, spark-ev-name, two-outlets-dead-friday, wholesale-trade-account
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
| escalation_precision | 78.6%, 81.0%, 80.5% | 80.0% | 1.3% | 78.6% to 81.0% | 3.1% | 5 of 129 |
| escalation_recall | 93.0%, 95.8%, 93.0% | 93.9% | 1.6% | 93.0% to 95.8% | 4.0% | 3 of 129 |
| health_safety_recall | 97.2%, 97.2%, 97.2% | 97.2% | 0.0% | 97.2% to 97.2% | 0.0% | 0 of 129 |
| primary_intent | 66.4%, 67.2%, 66.4% | 66.7% | 0.5% | 66.4% to 67.2% | 1.1% | 3 of 129 |
| route | 79.8%, 82.2%, 80.6% | 80.9% | 1.2% | 79.8% to 82.2% | 2.9% | 4 of 129 |
