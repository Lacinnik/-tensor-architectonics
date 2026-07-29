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

Version 0.5 improved RMSE against V_Bs, I_Q, Newell, and
Burton-O'Brien-McPherron by 9.02%, 6.65%, 4.15%, and 14.33% respectively.
It therefore failed the unchanged Newell RMSE gate. It also failed the
bootstrap gates against V_Bs, I_Q, and Newell, and the single-event
robustness gates against those same controls. All 80 registered events were
`SCORABLE`.

## Scientific conclusion

The implementation removes the former `HOLD-DATA` blockers and provides a
complete reproducible evaluation, but the available independent evidence
does not support `PASS`. The terminal result is `REJECT`.

## Reproduction

```bash
python -m unittest discover -s tools/eagc012 -p 'test_*.py'
python tools/eagc012/run_gate.py
```

The runner writes event-level predictions, fitted model parameters,
acceptance comparisons, provenance, and source hashes to
`artifacts/eagc012`.
