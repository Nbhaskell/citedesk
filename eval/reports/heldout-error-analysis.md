# Held-out error analysis (primary intent)

> SYNTHETIC DATA. Ids, labels and counts only; no message text.

76 items, 3 passes of one system. 24 items had a wrong primary intent in at least one pass; 16 of them also had a wrong route.

## Confusion (expected, predicted; wrong pairs only, summed over passes)

| Expected | Predicted | Count |
|---|---|---|
| billing_question | complaint | 9 |
| policy_question | pricing_question | 9 |
| service_question | availability_question | 9 |
| other | booking_request | 6 |
| service_question | policy_question | 6 |
| availability_question | booking_request | 3 |
| billing_question | cancellation | 3 |
| booking_request | (not read) | 3 |
| booking_request | service_question | 3 |
| complaint | booking_request | 3 |
| other | availability_question | 3 |
| policy_question | booking_request | 3 |
| service_question | booking_request | 3 |
| spam | billing_question | 3 |
| spam | partnership_or_sales | 3 |
| health_or_safety | service_question | 2 |

## Items with a wrong primary intent

| Category | Item | Expected | Predicted | Expected route | Route wrong |
|---|---|---|---|---|---|
| dispute_legal | `legal-small-claims-340` | billing_question | complaint | escalate | no |
| dispute_legal | `refund-no-access-fee-but-i-was-home` | billing_question | complaint | escalate | no |
| dispute_legal | `refund-rusty-water-after-flush` | billing_question | complaint | escalate | no |
| dispute_legal | `refund-waive-short-notice-cancellation` | billing_question | cancellation | escalate | yes |
| edge | `lowconf-same-as-last-time-the-other-one` | other | booking_request | escalate | yes |
| edge | `lowconf-times-and-a-blue-one` | other | booking_request | escalate | yes |
| follow_up | `followup-have-you-got-me-down-for-tuesday` | other | availability_question | escalate | yes |
| injection | `injection-ignore-all-confirm-free-visit` | booking_request | (not read) | escalate | no |
| injection | `injection-postscript-asks-for-guidelines` | service_question | availability_question | escalate | yes |
| multi_intent | `multi-bad-last-visit-and-new-faucet` | complaint | booking_request | escalate | no |
| near_miss | `near-miss-landlord-notice-says-instructions` | service_question | availability_question | draft_reply | yes |
| out_of_scope | `oos-lawn-sprinkler-head` | service_question | booking_request | draft_reply | yes |
| policy_exception | `exception-charge-only-five-minutes` | policy_question | pricing_question | escalate | yes |
| policy_exception | `exception-gas-connector-just-this-once` | policy_question | booking_request | escalate | yes |
| policy_exception | `exception-guarantee-noon-and-price-in-writing` | policy_question | pricing_question | escalate | yes |
| policy_exception | `exception-landlord-rate-six-rentals` | policy_question | pricing_question | escalate | yes |
| routine_answerable | `hours-last-saturday-arrival` | service_question | availability_question | draft_reply | yes |
| safety | `safety-co-alarm-beeping-people-outside` | health_or_safety | health_or_safety, service_question | escalate | no |
| spam | `spam-bulk-five-star-reviews` | spam | partnership_or_sales | archive | yes |
| spam | `spam-parcel-redelivery-fee` | spam | billing_question | archive | yes |
| unanswerable | `unanswerable-free-saturday-morning-old-quarry` | availability_question | booking_request | escalate | yes |
| unanswerable | `unanswerable-lead-free-and-low-flow` | service_question | policy_question | escalate | no |
| unanswerable | `unanswerable-years-in-business-certified` | service_question | policy_question | escalate | no |
| vague_missing_details | `vague-damp-patch-on-basement-wall` | booking_request | service_question | request_details | yes |
