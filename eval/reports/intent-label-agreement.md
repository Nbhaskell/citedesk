# Intent label agreement

> SYNTHETIC DATA. Ids, labels and counts only; no message text.

Second labeller: (not named). Sheet of 60 items; 60 labelled, 0 blank, 0 invalid.

- Exact agreement: 44 of 60 (73.3%)
- Cohen's kappa: 0.70
- Items marked unsure: 4; agreement on those 2 of 4, on the rest 42 of 56

## Disagreements by pair (existing label -> second labeller)

- billing_question -> complaint: 1
- billing_question -> other: 1
- billing_question -> policy_question: 1
- booking_request -> availability_question: 4
- booking_request -> booking_change: 1
- booking_request -> health_or_safety: 1
- booking_request -> other: 1
- other -> availability_question: 1
- other -> booking_request: 1
- pricing_question -> booking_request: 1
- pricing_question -> policy_question: 1
- service_question -> booking_request: 1
- service_question -> pricing_question: 1

## Disagreements by item

- vague-bathroom-remodel-quote: pricing_question -> booking_request
- refund-rusty-water-after-flush: billing_question -> complaint
- unanswerable-free-remodel-estimate: pricing_question -> policy_question
- safety-gas-mention-after-faucet-request: booking_request -> health_or_safety
- followup-is-friday-still-on: other -> availability_question
- billing-when-late-fee-starts: billing_question -> policy_question
- near-miss-landlord-notice-says-instructions: service_question -> booking_request
- injection-claimed-owner-refund: billing_question -> other (unsure)
- lowconf-times-and-a-blue-one: other -> booking_request
- booking-outer-area-travel-fee: booking_request -> availability_question
- urgent-no-hot-water-before-work: booking_request -> availability_question
- injection-ignore-all-confirm-free-visit: booking_request -> other (unsure)
- unanswerable-gas-water-heater-swap: service_question -> pricing_question
- near-miss-disregard-the-date-i-gave: booking_request -> booking_change
- urgent-toilet-wont-stop-running: booking_request -> availability_question
- urgent-landlord-deadline-toilet: booking_request -> availability_question

## Against the model

Items both labelled and read by the model: 33.

- Model right against the existing label: 30 of 33 (90.9%)
- Model right against the second labeller: 25 of 33 (75.8%)
- Of the 3 items the model got wrong against the existing label:
  - the second labeller sides with the model: 1 (doubt about the label)
  - the second labeller sides with the existing label: 2 (model error)
  - the second labeller agrees with neither: 0 (the item is hard)
- On the 26 items where both labellers agree, the model is right on 24 (92.3%)

## What this cannot tell you

- One extra labeller. Two people can agree and both be wrong, or differ on a rule that needs a decision.
- The existing labels were written by the author of the system. The second labeller reads the rules cold.
- A sample from the tuned and held-out splits, not the sealed set. The model was tuned on the tuned items, so its score against the existing labels is flattered there.
