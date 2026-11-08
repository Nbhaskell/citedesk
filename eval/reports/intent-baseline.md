# Intent baseline without a model

> SYNTHETIC DATA. Ids, intents and counts only; no message text.

Trained on the tuned split (135 items), scored once on the held-out split (76 items). Primary intent only. Method fixed before scoring (D-093).

| Method | Held-out | Tuned, leave-one-out |
|---|---|---|
| Majority | 14 of 76 (18.4%; 95% interval 11.3% to 28.6%) | 0 of 135 (0.0%; 95% interval 0.0% to 2.8%) |
| Naive Bayes | 39 of 76 (51.3%; 95% interval 40.3% to 62.2%) | 59 of 135 (43.7%; 95% interval 35.6% to 52.1%) |

Majority answer: `booking_request`. Leave-one-out is a poor guide for the majority method: when two intents are nearly as common, leaving one item out can change the answer to the other intent, so the method is wrong on every item. Read its held-out column.

## Naive Bayes errors on the held-out split (label -> baseline)

- health_or_safety -> booking_request: 5
- booking_request -> pricing_question: 4
- health_or_safety -> service_question: 3
- policy_question -> service_question: 3
- pricing_question -> service_question: 3
- other -> pricing_question: 2
- service_question -> pricing_question: 2
- availability_question -> booking_request: 1
- billing_question -> service_question: 1
- booking_request -> policy_question: 1
- booking_request -> service_question: 1
- cancellation -> complaint: 1
- complaint -> billing_question: 1
- complaint -> pricing_question: 1
- complaint -> service_question: 1
- other -> booking_request: 1
- partnership_or_sales -> pricing_question: 1
- policy_question -> billing_question: 1
- policy_question -> booking_request: 1
- spam -> billing_question: 1
- spam -> complaint: 1
- spam -> policy_question: 1

## Paired with model run `eval-heldout-heldout-20261029-203748-p1.run.json`

Items both answered: 75.
- Model right: 52 of 75 (69.3%; 95% interval 58.2% to 78.6%)
- Naive Bayes right: 39 of 75 (52.0%; 95% interval 40.9% to 62.9%)
- Both right 31, model only 21, baseline only 8, both wrong 15

## Paired with model run `eval-heldout-heldout-20261029-210109-p2.run.json`

Items both answered: 75.
- Model right: 52 of 75 (69.3%; 95% interval 58.2% to 78.6%)
- Naive Bayes right: 39 of 75 (52.0%; 95% interval 40.9% to 62.9%)
- Both right 31, model only 21, baseline only 8, both wrong 15

## Paired with model run `eval-heldout-heldout-20261029-212350-p3.run.json`

Items both answered: 75.
- Model right: 53 of 75 (70.7%; 95% interval 59.6% to 79.8%)
- Naive Bayes right: 39 of 75 (52.0%; 95% interval 40.9% to 62.9%)
- Both right 31, model only 22, baseline only 8, both wrong 14

## What this cannot tell you

- The held-out set is small and was written by the same author as the tuned set, so shared wording helps a word-count method as much as it helps the prompts.
- A saved model run is of the system as it was when that run was made.
- Primary intent only; routing, escalation and drafting are not compared.
