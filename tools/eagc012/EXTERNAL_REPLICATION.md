# EAGC-012 external SIR replication protocol

This document freezes the selection and evaluation protocol for version 0.6
before any target values from the external cohort are inspected. The previous
0.3, 0.4, and 0.5 `REJECT` decisions remain part of the validation history and
are not relabeled or replaced by this replication.

## Objective

Evaluate whether the frozen EAGC model specification transports from the
Richardson-Cane ICME cohorts to a distinct class of real solar-wind events:
stream interaction regions (SIRs), including recurrent CIRs, observed by Wind
and ACE.

This is event-catalog independence, not measurement-source independence. The
event definitions come from a different catalog and physical event class, while
the predictor and target measurements remain NASA OMNI one-minute observations
so that the models and acceptance gate are unchanged.

## Frozen catalog

- Catalog: Lan Jian, *Stream Interaction Regions (SIRs) from Wind and ACE Data
  during 1995-2009*, updated 2021-02-18.
- NASA/SPASE metadata:
  `https://spase-metadata.org/NASA/Catalog/Wind/SIR_List.html`
- Catalog PDF:
  `https://izw1.caltech.edu/ACE/ASC/DATA/level3/SIR_List_1995_2009_Jian.pdf`
- Catalog PDF SHA-256:
  `92540a56efd83d325df60011e0292d05305e1948c59fe3f78be96dd5c43bdb96`
- Method reference:
  `https://doi.org/10.1007/s11207-006-0132-3`

The catalog identifies SIRs using solar-wind signatures and does not publish
the SYM-H or Dst target used by this gate.

## Frozen candidate and window rules

1. Consider catalog rows from 1995 through 2002 in chronological order.
2. Exclude rows marked with `*`, which the catalog uses for SIRs containing or
   following an ICME or flux-rope-like structure.
3. Use the catalog `Start UT` as event start and `End UT` as the exclusive event
   end. Exclude fractional-minute timestamps rather than rounding them.
4. Set the forecast cutoff to exactly 12 hours after event start.
5. Require at least 12 target hours after the cutoff, so the complete catalog
   interval must be at least 24 hours.
6. Exclude a candidate if its half-open window overlaps any of the 80 events
   already disclosed by versions 0.3 through 0.5, or any earlier accepted
   external candidate.
7. Perform data-quality checks without computing, printing, or retaining target
   values or model scores. Require at least 75% prefix availability and no gap
   over 15 minutes for BY, BZ, speed, pressure, and SYM-H. Require at least 90%
   target SYM-H availability and no target gap over 15 minutes.
8. Accept the first 20 eligible candidates. Do not substitute events based on
   target magnitude, predictions, residuals, or acceptance results.

## Frozen model and acceptance gate

- Promote all 80 previously disclosed Richardson-Cane events to development.
- Keep the standardized-ridge feature set unchanged:
  `pressure_peak`, `log_Newell`, `pressure_recent`, and `south_hours`.
- Keep ridge `alpha=10.0`.
- Refit coefficients and all scalar control calibrations only on the 80-event
  development cohort.
- Keep all acceptance thresholds unchanged:
  at least 5% RMSE improvement against every required control, paired-bootstrap
  probability at least 0.90, and at least 5% improvement after omitting any
  one external event.
- After the 20-event cohort is frozen in `policy.json`, run the target-bearing
  gate exactly once. Record `PASS` only if every frozen criterion passes;
  otherwise record the returned `REJECT` or `HOLD-*` result without another
  selection or model iteration.

