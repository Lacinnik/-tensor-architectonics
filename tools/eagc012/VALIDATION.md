# EAGC-012 validation history

This file records every frozen independent evaluation performed while
implementing the EAGC-012 field gate. A failed validation is never relabeled
as `PASS` or removed from the history.

The acceptance criteria remained unchanged:

- at least 20 independent validation events;
- EAGC RMSE improvement of at least 5% against every required baseline;
- paired-bootstrap probability of improvement of at least 0.90;
- at least 5% improvement after omission of any one validation event.

## Frozen evaluations

| Version | Frozen commit | Development | Validation | EAGC RMSE | Best control RMSE | Decision |
|---|---:|---:|---:|---:|---:|---|
| 0.3 | `28db14a` | 20 | 20 | 43.1574 | Newell 42.4800 | `REJECT` |
| 0.4 | `c5c55d5` | 40 | 20 | 26.7723 | Newell 28.9018 | `REJECT` |
| 0.5 | `2d675f4` | 60 | 20 | 74.0301 | Newell 77.2362 | `REJECT` |
| 0.6 | `ea4d6d8` | 80 | 20 external SIRs | 21.3445 | Newell 17.2769 | `REJECT` |

Version 0.5 improved RMSE against V_Bs, I_Q, Newell, and
Burton-O'Brien-McPherron by 9.02%, 6.65%, 4.15%, and 14.33% respectively.
It therefore failed the unchanged Newell RMSE gate. It also failed the
bootstrap gates against V_Bs, I_Q, and Newell, and the single-event
robustness gates against those same controls. All 80 registered events were
`SCORABLE`.

Version 0.6 was preregistered in commit `ea06105`, and its 20-event external
SIR cohort was frozen in commit `ea4d6d8` before the target-bearing run. All
100 registered events were `SCORABLE`. EAGC improved RMSE over V_Bs and
Burton-O'Brien-McPherron by only 1.74% and 4.60%, was effectively tied with
I_Q, and was 23.54% worse than Newell. Every bootstrap probability was below
0.90, and every leave-one-validation-event-out robustness gate failed.

The version 0.6 result artifacts have these SHA-256 digests:

- `gate_metrics.json`:
  `537c36cf28f413270d311d1acc5f5ce55907d2d11566ef6901bd37005066ae3d`
- `event_summary.json`:
  `d0a91026f1825221588ce69464dec499b2fec40f19eab6ae51491d86953fed8b`
- `provenance.json`:
  `b6d22b2a7b75831ab72b7fe881dfda920dda1e9674f5ff324d1201ab606774ab`

## Scientific conclusion

The implementation removes the former `HOLD-DATA` blockers and provides a
complete reproducible evaluation, but the available independent evidence
does not support `PASS`. The external SIR transport test strengthens that
conclusion: the terminal result remains `REJECT`. No further event selection
or target-directed model iteration is permitted under the frozen version 0.6
protocol.

## Reproduction

```bash
python -m unittest discover -s tools/eagc012 -p 'test_*.py'
python tools/eagc012/run_gate.py
```

The runner writes event-level predictions, fitted model parameters,
acceptance comparisons, provenance, and source hashes to
`artifacts/eagc012`.

## Retrospective claim hierarchy

`SCIENTIFIC_ADJUDICATION.md` records a later threshold-sensitivity analysis
that does not alter any frozen decision or prediction. It makes Newell the
primary comparator and separates superiority, practical noninferiority, and
out-of-domain transport.

Under that explicitly retrospective policy, the frozen v0.5 ICME result is
`PASS-NONINFERIOR`: the +4.15% point improvement does not establish
superiority, but its 0.920 bootstrap probability of remaining within the
legacy 5% margin and its -0.71% worst single-event omission pass the
noninferiority rule. The v0.6 SIR result remains `TRANSPORT-REJECT`.

This interpretation is not presented as a new preregistered confirmation.
The machine-readable policy is `claim_policy.json`, and `adjudicate.py`
applies it directly to an immutable `gate_metrics.json` artifact without
refitting the model.
