# Internal GovDOSS option comparison

`kis4.compare.compare(record)` and `python -m kis4.compare` compare two to twenty
options without executing a recommendation. The installed command is
`kis4-compare`. No network, credential, identity provider or customer service is
called. Existing single-scorecard APIs and input semantics are unchanged.

## Input

The top-level object contains:

- `schema`: integer `1`.
- `as_of`: timezone-aware ISO8601 comparison time supplied by the caller.
- `max_age_hours`: integer from 1 to 8760, chosen before comparing options.
- `options`: two to twenty objects, each with a unique, nonblank `id` of at most
  128 characters; `evidence_observed_at`; `evidence_valid_until`; and `scorecard`.
- Each `scorecard` uses the existing schema demonstrated in
  `examples/scorecard.json`.

The scorecards must share one frozen rubric: rubric identifier, decision, owner,
dimension weights and rationale, threshold, dimension minimums, critical gate
identifiers, criterion identifiers and weights, principles, obligations, maturity
caps and optional `anchors`. Lists of gates and criteria may be reordered. These
rules are compared by canonical JSON, so a shared rubric name alone cannot hide
changed rules. A SHA256 digest identifies the frozen rules in the result; it is
not a signature or proof of approval.

Control implementations, test receipts, evidence, observed maturity, confidence
and scores may vary by option. Maturity caps in this comparison are shared scoring
rules. If an option cannot support its proposed score, lower the score or supply
evidence gaps; do not weaken the shared cap. Criterion coverage remains strict:
all material traceability is required before aggregation.

Missing, naive or invalid evidence times, future observations, age beyond the
declared limit, and evidence that has expired at `as_of` exclude the option. An
observation exactly `max_age_hours` old remains within the limit. Validity is
half-open: `observed_at <= as_of < valid_until`. One interval covers the option's
entire evidence bundle: callers must use the oldest observation and earliest
expiry among material evidence, or omit the interval when they cannot establish
it. Claiming a fresh date is not verification; no evidence URL is dereferenced.

## Results and sensitivity

`assessments` preserves each single-scorecard result and its exclusion reasons.
Missing evidence remains unknown, never zero. Failed or unknown critical gates,
material evidence gaps, freshness gaps and dimension-minimum violations exclude
the option from all rankings. A complete option below the composite threshold is
excluded from that scenario's ranking.

`baseline` reports descending score groups and `best_options`. Ties within
0.000001 are retained as ties and sorted by identifier for deterministic output;
there is no arbitrary tie-breaker. Displayed composite scores use six decimals.

`sensitivity` contains eight deterministic scenarios. Each dimension weight is
multiplied by 0.8 and 1.2 independently, then all weights are renormalized to sum
to one. Criterion scores, critical gates, maturity caps, dimension minimums and
the composite threshold remain unchanged. Each scenario reports its weights,
ranking, exclusions, winner changes and changes in rank order. An option may
cross the composite threshold under a scenario; that is reported, not concealed.
`rank_instability` includes changed order, ties and eligibility transitions.

The +/-20% rule is a diagnostic choice, not a confidence interval, probability,
prediction or proof of commercial effectiveness. The calculation tests weight
sensitivity only; it does not test the truth of evidence, the quality of criteria,
uncertain input scores, causal benefit or actual business outcomes.

CLI exits:

- `0`, `ready-for-review`: all options meet the stated gates and evidence rules;
  rankings remain stable under these perturbations.
- `1`, `review-sensitivity`: at least one scenario changes rank order or
  eligibility. A human must review the choice and uncertainty.
- `1`, `incomplete-comparison`: at least one baseline option is excluded, and no
  sensitivity change overrides this posture. The remaining ranking is conditional.
- `2`: malformed, oversized, non-finite, duplicate-key or incompatible input.

Every result sets `authority_granted=false` and
`evidence_independently_verified=false`. A stable winner does not approve a
purchase, merge, deployment or production readiness claim.

## Internal workflow

1. Define the decision, alternatives, scoring rules, evidence age and critical
   gates before assigning option scores.
2. Gather permitted test/build/operating evidence and distinguish observed facts
   from claims. Preserve the baseline and contrary evidence.
3. Populate the comparison record. Do not put secrets or customer records into it.
4. Run `python -m kis4.compare < examples/comparison.json` for the synthetic example,
   or supply the actual internal decision record.
5. Review exclusions, ties and sensitivity before recording a proposed decision.
6. Route that decision through the existing accountable owner and normal review
   gates. Record actual results in the next OODA cycle.

The example is synthetic and is never evidence that an option was deployed or
works for a customer. Dates are intentionally fixed for reproducible checks.
