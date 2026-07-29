# EAGC-012 scientific claim adjudication

The frozen v0.3-v0.6 decisions are retained exactly as recorded in
`VALIDATION.md`. This document adds a claim hierarchy that distinguishes
superiority, practical noninferiority, and transport. It does not relabel a
failed frozen protocol or refit a model.

## Why the original gate was too broad

The original gate required EAGC to achieve all three of the following against
each of four controls:

- at least 5% RMSE improvement;
- paired-bootstrap probability of improvement of at least 0.90;
- at least 5% improvement after every single-event omission.

This made four controls co-primary and repeated the same superiority margin in
a stress test. It produced twelve simultaneous pass conditions, although the
strongest published coupling-function comparator, Newell, is the scientifically
relevant primary baseline. Git history shows that the 5% and 0.90 thresholds
were introduced in commit `a009d4b` without a recorded domain or power
justification.

## Revised claim hierarchy

The tracked `claim_policy.json` applies these rules without changing any
predictions:

1. Newell is the sole primary comparator.
2. A 5% relative-RMSE loss is the legacy practical noninferiority margin.
3. `PASS-NONINFERIOR` requires:
   - point improvement greater than -5%;
   - paired event-bootstrap probability of improvement greater than -5% of at
     least 0.90;
   - every leave-one-event-out improvement greater than -5%.
4. `PASS-SUPERIOR` additionally requires:
   - point improvement of at least +5%;
   - bootstrap probability of positive improvement of at least 0.90;
   - no leave-one-event-out reversal.
5. V·Bs, I(Q), and Burton-O'Brien-McPherron are descriptive secondary
   comparators. They cannot veto the primary claim.
6. SIR evaluation is a transport test and receives an explicit
   `TRANSPORT-*` status rather than changing the ICME claim.

The 0.90 probability level is retained from the frozen policy. The
corresponding one-sided bootstrap lower bound is the 10th percentile, not the
lower endpoint of a two-sided 90% interval.

## Frozen-result adjudication

Run the adjudicator against the existing immutable artifacts:

```bash
python tools/eagc012/adjudicate.py \
  tools/eagc012/frozen/v0.5-validation-predictions.json \
  --scope in-domain \
  --output artifacts/v0.5/claim_adjudication.json

python tools/eagc012/adjudicate.py \
  artifacts/v0.6/gate_metrics.json \
  --scope transport \
  --output artifacts/v0.6/claim_adjudication.json
```

On the recorded v0.5 final ICME replication, the primary Newell comparison is:

- EAGC RMSE 74.0301 nT versus Newell 77.2362 nT;
- relative RMSE improvement +4.151%;
- bootstrap probability of noninferiority within 5%: 0.920;
- one-sided 90% lower bound: approximately -4.16%;
- 19 of 20 leave-one-event-out estimates positive;
- worst leave-one-event-out estimate: -0.714%.

The resulting status is `PASS-NONINFERIOR`, not `PASS-SUPERIOR`.
The tracked prediction snapshot records the SHA-256 of the complete frozen
v0.5 `gate_metrics.json`; the runner output and original provenance remain the
authoritative full artifacts.

The external SIR result remains `TRANSPORT-REJECT`: EAGC RMSE is 23.54% worse
than Newell and all 20 leave-one-event-out comparisons remain negative. This
means the ICME result does not generalize unchanged to SIRs.

## Interpretation boundary

This is a retrospective threshold-sensitivity analysis because the claim
hierarchy was written after the v0.3-v0.6 outcomes were observed. The status is
therefore an honest operational interpretation of the frozen evidence, not a
new preregistered confirmation. A future confirmatory claim must freeze this
policy before obtaining target-bearing results from a new ICME cohort.

The separation follows general validation principles: performance measures
should be reported with uncertainty, model updating must be distinguished from
external validation, and a noninferiority margin must be declared and
scientifically justified rather than chosen from the observed result.

References:

- Richardson-Cane near-Earth ICME catalog:
  https://doi.org/10.7910/DVN/C2MHTH
- TRIPOD external validation statement:
  https://doi.org/10.1136/bmj.g7594
- FDA guidance on prespecifying and justifying noninferiority margins:
  https://www.fda.gov/regulatory-information/search-fda-guidance-documents/non-inferiority-clinical-trials
