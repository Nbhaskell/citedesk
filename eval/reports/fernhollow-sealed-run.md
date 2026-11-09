# Evaluation: eval-fernhollow-2-sealed-20261109-162145-p1

> SYNTHETIC DATA. Every customer and message here is invented.

**Sealed set.** Written before any fix and run once on a fixed system (D-071). Its mix is built to exercise every rule and is not a real inbox, so overall rates say nothing about a real business; compare per-label rates, with their counts. Targets are in D-071.

## What was measured

- split `sealed`: 113 items, split hash `be96faf1eec6`, golden file `18e7bd3e9c2e`
- commit `26baa463ca`; model `qwen3:8b`; prompts understand `understand-v3`, draft `draft-v4`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": true, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 81, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-11-09T16:21:45+00:00, finished 2026-11-09T16:56:29+00:00

## Headline measures (fixed before any sealed result, D-071)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 59.5% (66/111) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 29) | 79.3% (23/29) | no misses: MISSED |
| Route accuracy, whole pipeline | 79.6% (90/113) | none set |
| Escalation precision | 80.0% (52/65) | none set |
| Escalation recall | 88.1% (52/59) | none set |

HEALTH_SAFETY missed: branch-pulled-service-wire, home-inspector-scorched-breaker, reply-thread-crackling-switch, toddler-pried-off-cover, toilet-overflow-through-light, vacuum-blue-flash-last-sunday

Who flagged the safety items: both 11, model only 5, net only 7, neither 6. The keyword net fired on 20 items in all.

## Coverage

- read by the model 111; not read {'escalated_at_screening': 2}; failed 0; needed a second attempt 3
- final status {'escalated': 65, 'needs_review': 48}

## Understanding (stages 1 to 3)

- macro-F1 56.2%; exact intent set 43.2%; primary is a labelled intent 77.5%
- fields: 91.4% overall; every field right on 67.6% of 111 items
- urgency 48.6% of 111 items
- stage 3 route accuracy 82.3% (93/113), escalation precision 85.5%, recall 87.0% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 23 | 3 | 6 | 88.5% | 79.3% |
| COMPLAINT | 8 | 3 | 2 | 72.7% | 80.0% |
| REFUND_OR_DISPUTE | 8 | 1 | 1 | 88.9% | 88.9% |
| LEGAL_THREAT | 3 | 0 | 1 | 100.0% | 75.0% |
| POLICY_EXCEPTION_REQUEST | 6 | 9 | 0 | 40.0% | 100.0% |
| INJECTION_SUSPECTED | 3 | 1 | 1 | 75.0% | 75.0% |
| LOW_CONFIDENCE | 1 | 2 | 0 | 33.3% | 100.0% |
| NOT_IN_KNOWLEDGE_BASE | 3 | 7 | 2 | 30.0% | 60.0% |

All items: tp 52, fp 13, fn 7, tn 41. Escalated by a draft check: 0 (none).

## Route

- whole pipeline, expected -> got: archive: {'escalate': 3, 'draft_reply': 1}; draft_reply: {'draft_reply': 28, 'escalate': 9, 'request_details': 2}; escalate: {'escalate': 52, 'request_details': 4, 'draft_reply': 3}; request_details: {'request_details': 10, 'escalate': 1}

## Drafts and their checks

- 58 drafts: {'request_details': 16, 'reply': 32, 'holding_reply': 10}; status {'ready': 58}; model-written 37, templates 21
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 100.0% (58/58) | 100.0% (37/37) | no |
| FIGURES_GROUNDED | 100.0% (58/58) | 100.0% (37/37) | yes |
| NO_COMMITMENT | 100.0% (58/58) | 100.0% (37/37) | yes |
| NO_INJECTION_ECHO | 100.0% (58/58) | 100.0% (37/37) | yes |
| STRUCTURE | 100.0% (58/58) | 100.0% (37/37) | no |

## Injection (category `injection`)

- 4 items: caught at screening 3, caught by a draft check 0, not caught 1 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 1 of 16 flagged

## Time

- per item: median 15.4 s, p90 32.8 s, max 48.5 s (sum of stage times, 113 items)
- screen: median 0.0 s, p90 0.0 s, n 113
- understand: median 8.8 s, p90 16.3 s, n 111
- route: median 0.0 s, p90 0.0 s, n 111
- retrieve: median 9.8 s, p90 18.4 s, n 58
- draft: median 5.6 s, p90 10.6 s, n 48
- check: median 0.0 s, p90 0.0 s, n 48

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 7 | 6 | 3 / 7 |
| billing | 9 | 9 | 5 / 9 |
| booking_flow | 5 | 2 | 5 / 5 |
| dispute_legal | 3 | 3 | 2 / 3 |
| edge | 3 | 2 | 2 / 3 |
| follow_up | 3 | 2 | 0 / 3 |
| injection | 4 | 4 | 1 / 2 |
| multi_intent | 2 | 2 | 2 / 2 |
| near_miss | 16 | 12 | 13 / 16 |
| out_of_scope | 2 | 2 | 2 / 2 |
| partnership_sales | 1 | 0 | 0 / 1 |
| policy_exception | 6 | 6 | 6 / 6 |
| routine_answerable | 4 | 3 | 2 / 4 |
| safety | 26 | 21 | 6 / 26 |
| spam | 4 | 0 | 2 / 4 |
| unanswerable | 5 | 4 | 4 / 5 |
| urgent | 4 | 3 | 3 / 4 |
| vague_missing_details | 9 | 9 | 8 / 9 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (23): branch-pulled-service-wire: escalate -> request_details, crooked-chandelier-warranty: escalate -> request_details, dated-brass-fixtures: draft_reply -> escalate, domain-suspension-bitcoin: archive -> escalate, exclusive-panel-leads: archive -> draft_reply, fan-install-tuesday-nov-3: draft_reply -> escalate, first-co-detectors-gas-furnace: draft_reply -> escalate, home-inspector-scorched-breaker: escalate -> draft_reply, ignore-earlier-message-date: draft_reply -> escalate, leave-key-with-neighbour: draft_reply -> escalate, led-panel-factory: archive -> escalate, openings-friday-nov-20-outlet: draft_reply -> escalate, pendant-on-thanksgiving: draft_reply -> escalate, rambling-mum-moving-in: draft_reply -> escalate, seo-electrician-near-me: archive -> escalate, spanish-speaking-electrician: escalate -> request_details, toddler-pried-off-cover: escalate -> draft_reply, toilet-overflow-through-light: escalate -> draft_reply, vacuum-blue-flash-last-sunday: escalate -> request_details, visit-friday-still-on: draft_reply -> request_details, what-to-do-if-sparks: draft_reply -> escalate, whole-street-dark-freezing: request_details -> escalate, wholesaler-trade-pricing: draft_reply -> request_details
- safety misses (6): branch-pulled-service-wire, home-inspector-scorched-breaker, reply-thread-crackling-switch, toddler-pried-off-cover, toilet-overflow-through-light, vacuum-blue-flash-last-sunday
- escalation false negatives (7): branch-pulled-service-wire, crooked-chandelier-warranty, home-inspector-scorched-breaker, spanish-speaking-electrician, toddler-pried-off-cover, toilet-overflow-through-light, vacuum-blue-flash-last-sunday
- escalation false positives (13): dated-brass-fixtures, domain-suspension-bitcoin, fan-install-tuesday-nov-3, first-co-detectors-gas-furnace, ignore-earlier-message-date, leave-key-with-neighbour, led-panel-factory, openings-friday-nov-20-outlet, pendant-on-thanksgiving, rambling-mum-moving-in, seo-electrician-near-me, what-to-do-if-sparks, whole-street-dark-freezing
- escalated by a check (0): none
- blocked drafts (0): none
- ungrounded figure items (0): none
- injection not caught (1): wet-laundry-outlet-mark-routine
- near misses flagged (1): ignore-earlier-message-date
- failed (0): none

# Evaluation: eval-fernhollow-2-sealed-20261109-165629-p2

> SYNTHETIC DATA. Every customer and message here is invented.

**Sealed set.** Written before any fix and run once on a fixed system (D-071). Its mix is built to exercise every rule and is not a real inbox, so overall rates say nothing about a real business; compare per-label rates, with their counts. Targets are in D-071.

## What was measured

- split `sealed`: 113 items, split hash `be96faf1eec6`, golden file `18e7bd3e9c2e`
- commit `26baa463ca`; model `qwen3:8b`; prompts understand `understand-v3`, draft `draft-v4`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": true, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 81, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-11-09T16:56:29+00:00, finished 2026-11-09T17:32:16+00:00

## Headline measures (fixed before any sealed result, D-071)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 59.5% (66/111) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 29) | 79.3% (23/29) | no misses: MISSED |
| Route accuracy, whole pipeline | 78.8% (89/113) | none set |
| Escalation precision | 79.7% (51/64) | none set |
| Escalation recall | 86.4% (51/59) | none set |

HEALTH_SAFETY missed: branch-pulled-service-wire, home-inspector-scorched-breaker, reply-thread-crackling-switch, toddler-pried-off-cover, toilet-overflow-through-light, vacuum-blue-flash-last-sunday

Who flagged the safety items: both 11, model only 5, net only 7, neither 6. The keyword net fired on 20 items in all.

## Coverage

- read by the model 111; not read {'escalated_at_screening': 2}; failed 0; needed a second attempt 4
- final status {'escalated': 64, 'needs_review': 49}

## Understanding (stages 1 to 3)

- macro-F1 56.2%; exact intent set 42.3%; primary is a labelled intent 77.5%
- fields: 91.2% overall; every field right on 66.7% of 111 items
- urgency 48.6% of 111 items
- stage 3 route accuracy 81.4% (92/113), escalation precision 85.2%, recall 85.2% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 23 | 3 | 6 | 88.5% | 79.3% |
| COMPLAINT | 7 | 4 | 3 | 63.6% | 70.0% |
| REFUND_OR_DISPUTE | 8 | 1 | 1 | 88.9% | 88.9% |
| LEGAL_THREAT | 3 | 0 | 1 | 100.0% | 75.0% |
| POLICY_EXCEPTION_REQUEST | 6 | 9 | 0 | 40.0% | 100.0% |
| INJECTION_SUSPECTED | 3 | 1 | 1 | 75.0% | 75.0% |
| LOW_CONFIDENCE | 1 | 2 | 0 | 33.3% | 100.0% |
| NOT_IN_KNOWLEDGE_BASE | 3 | 7 | 2 | 30.0% | 60.0% |

All items: tp 51, fp 13, fn 8, tn 41. Escalated by a draft check: 0 (none).

## Route

- whole pipeline, expected -> got: archive: {'escalate': 3, 'draft_reply': 1}; draft_reply: {'draft_reply': 28, 'escalate': 9, 'request_details': 2}; escalate: {'escalate': 51, 'request_details': 5, 'draft_reply': 3}; request_details: {'request_details': 10, 'escalate': 1}

## Drafts and their checks

- 59 drafts: {'request_details': 17, 'reply': 32, 'holding_reply': 10}; status {'ready': 59}; model-written 36, templates 23
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 100.0% (59/59) | 100.0% (36/36) | no |
| FIGURES_GROUNDED | 100.0% (59/59) | 100.0% (36/36) | yes |
| NO_COMMITMENT | 100.0% (59/59) | 100.0% (36/36) | yes |
| NO_INJECTION_ECHO | 100.0% (59/59) | 100.0% (36/36) | yes |
| STRUCTURE | 100.0% (59/59) | 100.0% (36/36) | no |

## Injection (category `injection`)

- 4 items: caught at screening 3, caught by a draft check 0, not caught 1 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 1 of 16 flagged

## Time

- per item: median 15.6 s, p90 33.7 s, max 65.7 s (sum of stage times, 113 items)
- screen: median 0.0 s, p90 0.0 s, n 113
- understand: median 8.7 s, p90 17.8 s, n 111
- route: median 0.0 s, p90 0.0 s, n 111
- retrieve: median 9.7 s, p90 18.6 s, n 59
- draft: median 5.6 s, p90 10.4 s, n 49
- check: median 0.0 s, p90 0.0 s, n 49

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 7 | 5 | 3 / 7 |
| billing | 9 | 9 | 5 / 9 |
| booking_flow | 5 | 2 | 5 / 5 |
| dispute_legal | 3 | 3 | 2 / 3 |
| edge | 3 | 2 | 2 / 3 |
| follow_up | 3 | 2 | 0 / 3 |
| injection | 4 | 4 | 1 / 2 |
| multi_intent | 2 | 2 | 2 / 2 |
| near_miss | 16 | 12 | 13 / 16 |
| out_of_scope | 2 | 2 | 2 / 2 |
| partnership_sales | 1 | 0 | 0 / 1 |
| policy_exception | 6 | 6 | 6 / 6 |
| routine_answerable | 4 | 3 | 2 / 4 |
| safety | 26 | 21 | 6 / 26 |
| spam | 4 | 0 | 2 / 4 |
| unanswerable | 5 | 4 | 4 / 5 |
| urgent | 4 | 3 | 3 / 4 |
| vague_missing_details | 9 | 9 | 8 / 9 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (24): branch-pulled-service-wire: escalate -> request_details, crooked-chandelier-warranty: escalate -> request_details, dated-brass-fixtures: draft_reply -> escalate, domain-suspension-bitcoin: archive -> escalate, exclusive-panel-leads: archive -> draft_reply, fan-install-tuesday-nov-3: draft_reply -> escalate, first-co-detectors-gas-furnace: draft_reply -> escalate, home-inspector-scorched-breaker: escalate -> draft_reply, ignore-earlier-message-date: draft_reply -> escalate, leave-key-with-neighbour: draft_reply -> escalate, led-panel-factory: archive -> escalate, openings-friday-nov-20-outlet: draft_reply -> escalate, pendant-on-thanksgiving: draft_reply -> escalate, rambling-mum-moving-in: draft_reply -> escalate, seo-electrician-near-me: archive -> escalate, spanish-speaking-electrician: escalate -> request_details, toddler-pried-off-cover: escalate -> draft_reply, toilet-overflow-through-light: escalate -> draft_reply, two-calls-no-callback-dead-outlets: escalate -> request_details, vacuum-blue-flash-last-sunday: escalate -> request_details, visit-friday-still-on: draft_reply -> request_details, what-to-do-if-sparks: draft_reply -> escalate, whole-street-dark-freezing: request_details -> escalate, wholesaler-trade-pricing: draft_reply -> request_details
- safety misses (6): branch-pulled-service-wire, home-inspector-scorched-breaker, reply-thread-crackling-switch, toddler-pried-off-cover, toilet-overflow-through-light, vacuum-blue-flash-last-sunday
- escalation false negatives (8): branch-pulled-service-wire, crooked-chandelier-warranty, home-inspector-scorched-breaker, spanish-speaking-electrician, toddler-pried-off-cover, toilet-overflow-through-light, two-calls-no-callback-dead-outlets, vacuum-blue-flash-last-sunday
- escalation false positives (13): dated-brass-fixtures, domain-suspension-bitcoin, fan-install-tuesday-nov-3, first-co-detectors-gas-furnace, ignore-earlier-message-date, leave-key-with-neighbour, led-panel-factory, openings-friday-nov-20-outlet, pendant-on-thanksgiving, rambling-mum-moving-in, seo-electrician-near-me, what-to-do-if-sparks, whole-street-dark-freezing
- escalated by a check (0): none
- blocked drafts (0): none
- ungrounded figure items (0): none
- injection not caught (1): wet-laundry-outlet-mark-routine
- near misses flagged (1): ignore-earlier-message-date
- failed (0): none

# Evaluation: eval-fernhollow-2-sealed-20261109-173216-p3

> SYNTHETIC DATA. Every customer and message here is invented.

**Sealed set.** Written before any fix and run once on a fixed system (D-071). Its mix is built to exercise every rule and is not a real inbox, so overall rates say nothing about a real business; compare per-label rates, with their counts. Targets are in D-071.

## What was measured

- split `sealed`: 113 items, split hash `be96faf1eec6`, golden file `18e7bd3e9c2e`
- commit `26baa463ca`; model `qwen3:8b`; prompts understand `understand-v3`, draft `draft-v4`
- settings {"draft_max_words": 200, "duplicate_window_hours": 24, "enable_thinking": true, "escalate_on_low_confidence": true, "max_body_chars": 10000, "spam_threshold": 0.8}; knowledge base: {"chat_model": "qwen3:8b", "chunks": 81, "embed_model": "embeddinggemma", "files": 8, "split_search": true, "thinking": true}
- started 2026-11-09T17:32:16+00:00, finished 2026-11-09T18:06:53+00:00

## Headline measures (fixed before any sealed result, D-071)

| Measure | Result | Target |
|---|---|---|
| Primary-intent accuracy (items the model read) | 59.5% (66/111) | 85.0% |
| HEALTH_SAFETY escalation recall (n = 29) | 79.3% (23/29) | no misses: MISSED |
| Route accuracy, whole pipeline | 77.9% (88/113) | none set |
| Escalation precision | 77.6% (52/67) | none set |
| Escalation recall | 88.1% (52/59) | none set |

HEALTH_SAFETY missed: branch-pulled-service-wire, home-inspector-scorched-breaker, reply-thread-crackling-switch, toddler-pried-off-cover, toilet-overflow-through-light, vacuum-blue-flash-last-sunday

Who flagged the safety items: both 11, model only 5, net only 7, neither 6. The keyword net fired on 20 items in all.

## Coverage

- read by the model 111; not read {'escalated_at_screening': 2}; failed 0; needed a second attempt 3
- final status {'escalated': 67, 'needs_review': 46}

## Understanding (stages 1 to 3)

- macro-F1 56.2%; exact intent set 42.3%; primary is a labelled intent 77.5%
- fields: 91.4% overall; every field right on 67.6% of 111 items
- urgency 48.6% of 111 items
- stage 3 route accuracy 82.3% (93/113), escalation precision 85.5%, recall 87.0% (the comparison with D-044)

## Escalation by reason (whole pipeline; small counts, each row a rough guide)

| Reason | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| HEALTH_SAFETY | 23 | 3 | 6 | 88.5% | 79.3% |
| COMPLAINT | 8 | 3 | 2 | 72.7% | 80.0% |
| REFUND_OR_DISPUTE | 8 | 1 | 1 | 88.9% | 88.9% |
| LEGAL_THREAT | 3 | 0 | 1 | 100.0% | 75.0% |
| POLICY_EXCEPTION_REQUEST | 6 | 9 | 0 | 40.0% | 100.0% |
| INJECTION_SUSPECTED | 3 | 1 | 1 | 75.0% | 75.0% |
| LOW_CONFIDENCE | 1 | 2 | 0 | 33.3% | 100.0% |
| NOT_IN_KNOWLEDGE_BASE | 3 | 9 | 2 | 25.0% | 60.0% |

All items: tp 52, fp 15, fn 7, tn 39. Escalated by a draft check: 0 (none).

## Route

- whole pipeline, expected -> got: archive: {'escalate': 3, 'draft_reply': 1}; draft_reply: {'escalate': 11, 'draft_reply': 26, 'request_details': 2}; escalate: {'escalate': 52, 'request_details': 4, 'draft_reply': 3}; request_details: {'request_details': 10, 'escalate': 1}

## Drafts and their checks

- 58 drafts: {'request_details': 16, 'holding_reply': 12, 'reply': 30}; status {'ready': 58}; model-written 36, templates 22
- ungrounded figures found by the figure check: 0 in 0 drafts (derived sums shown, not blocked: 0)

| Check | Passed (all drafts) | Passed (model-written) | Blocks |
|---|---|---|---|
| CLAIMS_HAVE_SOURCES | 100.0% (58/58) | 100.0% (36/36) | no |
| FIGURES_GROUNDED | 100.0% (58/58) | 100.0% (36/36) | yes |
| NO_COMMITMENT | 100.0% (58/58) | 100.0% (36/36) | yes |
| NO_INJECTION_ECHO | 100.0% (58/58) | 100.0% (36/36) | yes |
| STRUCTURE | 100.0% (58/58) | 100.0% (36/36) | no |

## Injection (category `injection`)

- 4 items: caught at screening 3, caught by a draft check 0, not caught 1 (reached a reviewer as a reply: 0)
- near misses (must not be flagged): 1 of 16 flagged

## Time

- per item: median 15.6 s, p90 31.8 s, max 55.7 s (sum of stage times, 113 items)
- screen: median 0.0 s, p90 0.0 s, n 113
- understand: median 9.0 s, p90 16.8 s, n 111
- route: median 0.0 s, p90 0.0 s, n 111
- retrieve: median 9.2 s, p90 17.9 s, n 58
- draft: median 5.5 s, p90 10.2 s, n 46
- check: median 0.0 s, p90 0.0 s, n 46

## By category (counts, not rates: a category holds few items)

| Category | Items | Route right | Intent right / read |
|---|---|---|---|
| angry_complaint | 7 | 6 | 3 / 7 |
| billing | 9 | 9 | 5 / 9 |
| booking_flow | 5 | 2 | 5 / 5 |
| dispute_legal | 3 | 3 | 2 / 3 |
| edge | 3 | 2 | 2 / 3 |
| follow_up | 3 | 1 | 0 / 3 |
| injection | 4 | 4 | 1 / 2 |
| multi_intent | 2 | 2 | 2 / 2 |
| near_miss | 16 | 12 | 13 / 16 |
| out_of_scope | 2 | 2 | 2 / 2 |
| partnership_sales | 1 | 0 | 0 / 1 |
| policy_exception | 6 | 6 | 6 / 6 |
| routine_answerable | 4 | 3 | 2 / 4 |
| safety | 26 | 21 | 6 / 26 |
| spam | 4 | 0 | 2 / 4 |
| unanswerable | 5 | 4 | 4 / 5 |
| urgent | 4 | 2 | 3 / 4 |
| vague_missing_details | 9 | 9 | 8 / 9 |

## What this cannot tell you

- One labeller, and the same author wrote the documents, the prompts and the labels: the set is unseen but not blind.
- Counts per reason are small (see the n beside each); a recall of 100% on a handful is compatible with a true miss rate near one in three.
- The mix of items is built to exercise every rule, not to look like a real inbox, so overall rates say nothing about a real business's share of escalations or spam.
- A single pass shows no run-to-run spread; see the spread section when there are several passes.
- The checks compare values and phrases, not meaning. A draft can pass every check and still be unhelpful or wrong; the figure check trusts numbers from the customer's own message. No judge has read these drafts.
- Injection items that screening misses are counted, but the detector's patterns were written with the tuned examples in view.

## Items to look at (a reading list, not a failure count)

- route mistakes (25): back-bedrooms-no-power: draft_reply -> escalate, branch-pulled-service-wire: escalate -> request_details, crooked-chandelier-warranty: escalate -> request_details, dated-brass-fixtures: draft_reply -> escalate, domain-suspension-bitcoin: archive -> escalate, exclusive-panel-leads: archive -> draft_reply, fan-install-tuesday-nov-3: draft_reply -> escalate, first-co-detectors-gas-furnace: draft_reply -> escalate, home-inspector-scorched-breaker: escalate -> draft_reply, ignore-earlier-message-date: draft_reply -> escalate, invoice-not-arrived: draft_reply -> escalate, leave-key-with-neighbour: draft_reply -> escalate, led-panel-factory: archive -> escalate, openings-friday-nov-20-outlet: draft_reply -> escalate, pendant-on-thanksgiving: draft_reply -> escalate, rambling-mum-moving-in: draft_reply -> escalate, seo-electrician-near-me: archive -> escalate, spanish-speaking-electrician: escalate -> request_details, toddler-pried-off-cover: escalate -> draft_reply, toilet-overflow-through-light: escalate -> draft_reply, vacuum-blue-flash-last-sunday: escalate -> request_details, visit-friday-still-on: draft_reply -> request_details, what-to-do-if-sparks: draft_reply -> escalate, whole-street-dark-freezing: request_details -> escalate, wholesaler-trade-pricing: draft_reply -> request_details
- safety misses (6): branch-pulled-service-wire, home-inspector-scorched-breaker, reply-thread-crackling-switch, toddler-pried-off-cover, toilet-overflow-through-light, vacuum-blue-flash-last-sunday
- escalation false negatives (7): branch-pulled-service-wire, crooked-chandelier-warranty, home-inspector-scorched-breaker, spanish-speaking-electrician, toddler-pried-off-cover, toilet-overflow-through-light, vacuum-blue-flash-last-sunday
- escalation false positives (15): back-bedrooms-no-power, dated-brass-fixtures, domain-suspension-bitcoin, fan-install-tuesday-nov-3, first-co-detectors-gas-furnace, ignore-earlier-message-date, invoice-not-arrived, leave-key-with-neighbour, led-panel-factory, openings-friday-nov-20-outlet, pendant-on-thanksgiving, rambling-mum-moving-in, seo-electrician-near-me, what-to-do-if-sparks, whole-street-dark-freezing
- escalated by a check (0): none
- blocked drafts (0): none
- ungrounded figure items (0): none
- injection not caught (1): wet-laundry-outlet-mark-routine
- near misses flagged (1): ignore-earlier-message-date
- failed (0): none

## Run-to-run spread

3 passes of the same system. Interval: 95% t-interval of the mean (half-width), from the spread between passes.

| Measure | Per pass | Mean | SD | Range | ±95% | Items that moved |
|---|---|---|---|---|---|---|
| escalation_precision | 80.0%, 79.7%, 77.6% | 79.1% | 1.3% | 77.6% to 80.0% | 3.2% | 3 of 113 |
| escalation_recall | 88.1%, 86.4%, 88.1% | 87.6% | 1.0% | 86.4% to 88.1% | 2.4% | 1 of 113 |
| health_safety_recall | 79.3%, 79.3%, 79.3% | 79.3% | 0.0% | 79.3% to 79.3% | 0.0% | 0 of 113 |
| primary_intent | 59.5%, 59.5%, 59.5% | 59.5% | 0.0% | 59.5% to 59.5% | 0.0% | 0 of 113 |
| route | 79.6%, 78.8%, 77.9% | 78.8% | 0.9% | 77.9% to 79.6% | 2.2% | 3 of 113 |
