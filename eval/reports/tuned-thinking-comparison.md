# Comparison: think-off against think-on

> SYNTHETIC DATA. Every customer and message here is invented.

- think-off: 3 passes; think-on: 3 passes; split `tuned`, hash `e565a01fb73a`
- the setting that differs: enable_thinking = False against True

A difference is **real** only if it is larger than the 95% t-interval from the spread between passes **and** a paired bootstrap over items (resampling the same items for both settings) excludes zero. Meeting only one is **unclear**, which is not the same as no effect. Differences are in percentage points, first minus second.

| Measure | think-off (mean, ±95%) | think-on (mean, ±95%) | Difference | Pass interval ± | Bootstrap 95% | Call |
|---|---|---|---|---|---|---|
| primary_intent | 77.2% ± 0.0% | 83.5% ± 1.2% | -6.2 pp | 1.2% | -13.8 pp to +0.8 pp | unclear |
| route | 74.3% ± 2.8% | 78.0% ± 2.8% | -3.7 pp | 2.6% | -8.6 pp to +1.0 pp | unclear |
| escalation_precision | 70.5% ± 4.4% | 71.6% ± 2.9% | -1.1 pp | 3.9% | -7.9 pp to +5.6 pp | unclear |
| escalation_recall | 78.0% ± 3.1% | 82.3% ± 6.1% | -4.3 pp | 6.8% | -13.7 pp to +4.4 pp | unclear |
| health_safety_recall | 100.0% ± 0.0% | 100.0% ± 0.0% | +0.0 pp | 0.0% | +0.0 pp to +0.0 pp | unclear |

## What the test could have seen

- primary_intent: unclear; the paired bootstrap includes zero. Differences under about +7.3 pp could not have been seen.
- route: unclear; the paired bootstrap includes zero. Differences under about +4.8 pp could not have been seen.
- escalation_precision: unclear; the difference is within the pass spread and the paired bootstrap includes zero. Differences under about +6.7 pp could not have been seen.
- escalation_recall: unclear; the difference is within the pass spread and the paired bootstrap includes zero. Differences under about +9.0 pp could not have been seen.
- health_safety_recall: unclear; the difference is within the pass spread and the paired bootstrap includes zero. Note: the passes had no spread between them, so only the bootstrap decides.

## What this cannot tell you

- The passes use a fixed seed, so run-to-run spread may be small for reasons that do not hold on another machine or with another seed; a zero spread leaves the call to the bootstrap alone.
- The bootstrap resamples these items. It says nothing about customers who write differently, and one labeller wrote every label.
- Health-and-safety recall rests on a handful of items, so it can only show a large difference.
- Thinking applies to the understand step only here; rag-project's own thinking setting is recorded in each run and was the same in both groups.
