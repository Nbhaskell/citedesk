# Intent baseline without a model

> SYNTHETIC DATA. Ids, intents and counts only; no message text.

Trained on the tuned split (135 items), scored once on the held-out split (83 items). Primary intent only. Method fixed before scoring (D-093).

| Method | Held-out | Tuned, leave-one-out |
|---|---|---|
| Majority | 16 of 83 (19.3%; 95% interval 12.2% to 29.0%) | 0 of 135 (0.0%; 95% interval 0.0% to 2.8%) |
| Naive Bayes | 49 of 83 (59.0%; 95% interval 48.3% to 69.0%) | 59 of 135 (43.7%; 95% interval 35.6% to 52.1%) |

Majority answer: `booking_request`. Leave-one-out is a poor guide for the majority method: when two intents are nearly as common, leaving one item out can change the answer to the other intent, so the method is wrong on every item. Read its held-out column.

## Naive Bayes errors on the held-out split (label -> baseline)

- health_or_safety -> booking_request: 5
- service_question -> pricing_question: 5
- pricing_question -> policy_question: 4
- health_or_safety -> pricing_question: 2
- health_or_safety -> service_question: 2
- availability_question -> pricing_question: 1
- billing_question -> pricing_question: 1
- booking_change -> booking_request: 1
- booking_request -> pricing_question: 1
- booking_request -> service_question: 1
- cancellation -> billing_question: 1
- complaint -> billing_question: 1
- complaint -> service_question: 1
- health_or_safety -> billing_question: 1
- partnership_or_sales -> pricing_question: 1
- pricing_question -> billing_question: 1
- pricing_question -> service_question: 1
- service_question -> booking_request: 1
- spam -> complaint: 1
- spam -> pricing_question: 1
- spam -> service_question: 1

## Paired with model run `eval-fernhollow-heldout-20261109-010743-p1.run.json`

Items both answered: 82.
- Model right: 58 of 82 (70.7%; 95% interval 60.1% to 79.5%)
- Naive Bayes right: 48 of 82 (58.5%; 95% interval 47.7% to 68.6%)
- Both right 35, model only 23, baseline only 13, both wrong 11

## Paired with model run `eval-fernhollow-heldout-20261109-013050-p2.run.json`

Items both answered: 82.
- Model right: 58 of 82 (70.7%; 95% interval 60.1% to 79.5%)
- Naive Bayes right: 48 of 82 (58.5%; 95% interval 47.7% to 68.6%)
- Both right 35, model only 23, baseline only 13, both wrong 11

## Paired with model run `eval-fernhollow-heldout-20261109-015355-p3.run.json`

Items both answered: 82.
- Model right: 58 of 82 (70.7%; 95% interval 60.1% to 79.5%)
- Naive Bayes right: 48 of 82 (58.5%; 95% interval 47.7% to 68.6%)
- Both right 35, model only 23, baseline only 13, both wrong 11

## What this cannot tell you

- The test items come from another file (`--test-golden`), such as another business's set, while training and leave-one-out stay on the tuned items of `--golden`. Words that belong to one trade do not carry to another, which costs a word-count method more than the prompts.
- A saved model run is of the system as it was when that run was made.
- Primary intent only; routing, escalation and drafting are not compared.
