# EAGC-012 confirmatory ICME protocol v1.0

This package preregisters a strictly prospective, near-Earth ICME confirmation after the retrospective EAGC-012 adjudication. It is **ready to accrue**, not ready to score: no post-freeze event and no new target value is present in this pull request.

## Immutable boundary

The protocol freeze is the first Git commit containing `TZAR-RESEARCH-EAGC-012-CONFIRMATORY-ICME` version `1.0.0-prospective` at `tools/eagc012/confirmatory_icme_protocol.json`. Only Wind ICMEs whose event start and catalog-snapshot retrieval are strictly later than that commit timestamp can enter the cohort.

Any material amendment creates a new version and restarts prospective accrual after the new introducing commit. Editing this version cannot rescue an observed result.

## Target-blind accrual

Use the highest officially linked HELIO4CAST ICMECAT version (minimum 2.3) only through the four-column projection `icmecat_id`, `sc_insitu`, `icme_start_time`, and `mo_end_time`. Select the first 20 eligible Wind rows in deterministic chronological order. Freeze the complete event manifest, exact versioned source URL, source snapshot hash, projection hash, and retrieval timestamps in an earlier commit before requesting OMNI data for any selected window.

Selected events are never replaced. Missing or late target data yield `HOLD`; they do not cause a more favorable event to be substituted.

## Frozen analysis

- Cutoff: 12 hours after `icme_start_time`.
- Target: minimum SYM-H in `[cutoff, mo_end_time)`.
- EAGC: standardized ridge, alpha 10, features `pressure_peak`, `log_Newell`, `pressure_recent`, and `south_hours`.
- Training: the 80 previously disclosed ICME development events only.
- Primary baseline: Newell.
- Secondary descriptive controls: V·Bs, I(Q), and Burton–O'Brien–McPherron.

`PASS-NONINFERIOR` uses the preregistered 5% relative-RMSE margin, paired event bootstrap probability of at least 0.90, and a leave-one-event-out worst case inside the same margin. `PASS-SUPERIOR` additionally requires at least 5% point improvement, bootstrap probability of positive improvement of at least 0.90, and no leave-one-event-out reversal. Otherwise a complete cohort is `REJECT`; incomplete data or broken provenance are `HOLD`.

No result is transferable to SIR. The previously observed SIR result remains `TRANSPORT-REJECT` and is outside this confirmatory claim.

## Verification

```bash
python tools/eagc012/validate_confirmatory_protocol.py
python -m unittest discover -s tools/eagc012 -p 'test_confirmatory_protocol.py'
```

The validator fails closed on target access before manifest freeze, event replacement, SIR transfer, model drift, relaxed superiority criteria, or incomplete reproducibility requirements.

When a new official ICMECAT snapshot appears, build the target-blind candidate manifest without retaining any non-allowlisted column:

```bash
python tools/eagc012/accrue_confirmatory_cohort.py ICMECAT.csv \
  --source-url <exact-versioned-url> \
  --source-version <version> \
  --retrieved-at <UTC> \
  --freeze-commit <introducing-commit> \
  --freeze-committed-at <UTC> \
  --output tools/eagc012/frozen/confirmatory-icme-v1-events.json
```

Even a complete candidate manifest keeps `target_access_permitted: false`; target retrieval is a later, separately committed step.
