# EAGC-012 confirmatory ICME protocol v1.1

Version `1.0.0-prospective` is preserved unchanged and registered as
`SUPERSEDED-BEFORE-ACCRUAL`. The active contract is
`TZAR-RESEARCH-EAGC-012-CONFIRMATORY-ICME` `1.1.0-prospective`.

The protocol is ready only for target-blind accrual. It is not ready to query
selected OMNI windows or score a claim until the required commits exist.

## Immutable boundary

The freeze anchor is resolved from Git history: the earliest commit containing
the v1.1 protocol ID and version at
`tools/eagc012/confirmatory_icme_protocol_v1.1.0.json`. Validation requires the
current protocol bytes to equal the bytes at that commit. Manual freeze SHA or
timestamp input is not accepted.

Any material amendment requires another version and another prospective
cohort. The v1.1 model parameters, training-source hashes, bootstrap index
matrix, decision inequalities and implementation hashes are frozen artifacts.

## State transitions

1. `FROZEN-PRE-TARGET → OPEN-ACCRUAL`: validate protocol and Git anchor.
2. `OPEN-ACCRUAL → MANIFEST-CANDIDATE`: process official ICMECAT versions in
   ascending order and append exactly 20 eligible events.
3. Commit the exact manifest.
4. Generate `TARGET-AUTHORIZATION-CANDIDATE` from that committed manifest.
5. Commit the exact authorization in a later descendant commit.
6. Only then may the data preparer request selected OMNI windows.
7. Score with the frozen model and bootstrap matrix; never refit.

Any broken provenance, chronology, source, catalog, data-quality, model or
decision invariant yields `HOLD`.

## Target-blind accrual

```bash
python tools/eagc012/accrue_confirmatory_cohort.py \
  --output tools/eagc012/frozen/confirmatory-icme-v1.1-events.json
```

The runner reads the official landing page, obtains exact versioned URLs,
rechecks previously processed source hashes and processes every unprocessed
version in semantic order. Only `icmecat_id`, `sc_insitu`, `icme_start_time`
and `mo_end_time` enter the manifest.

Each first-seen post-freeze Wind row receives a permanent decision. Previously
selected or skipped rows cannot change. A catalog correction produces
`HOLD-CATALOG-REVISION`; changed bytes at the same versioned URL produce
`HOLD-SOURCE-MUTATION`. Every non-initial accrual run requires the previous
manifest bytes to exist in Git history and records that parent evidence.

## Target authorization

After the complete manifest has been committed:

```bash
python tools/eagc012/authorize_confirmatory_target.py
git add tools/eagc012/frozen/confirmatory-icme-v1.1-target-authorization.json
git commit
```

The authorization file is inert while uncommitted. The data preparer proves
that the manifest commit is an ancestor of the later authorization commit
before making its first OMNI request.

## Data preparation and scoring

```bash
python tools/eagc012/prepare_confirmatory_data.py \
  --output artifacts/eagc012/confirmatory-v1.1-event-summary.json

python tools/eagc012/score_confirmatory_cohort.py \
  artifacts/eagc012/confirmatory-v1.1-event-summary.json \
  --output artifacts/eagc012/confirmatory-v1.1-adjudication.json
```

The fixed primary statistic is

`(RMSE_Newell - RMSE_EAGC) / RMSE_Newell`.

`PASS-NONINFERIOR` requires a point value strictly greater than `-0.05`, a
frozen-index bootstrap probability of at least `0.90` for values strictly
greater than `-0.05`, and every leave-one-event-out value strictly greater than
`-0.05`.

`PASS-SUPERIOR` additionally requires point improvement at least `0.05`,
bootstrap probability at least `0.90` for improvement strictly greater than
zero, and no leave-one-event-out value at or below zero. Otherwise a complete,
provenance-valid cohort is `REJECT`; incomplete or invalid evidence is `HOLD`.

## Verification

```bash
python -m unittest discover -s tools/eagc012 -p 'test_*.py'
python tools/eagc012/validate_confirmatory_protocol.py
```

The second command requires full Git history. CI checks out with
`fetch-depth: 0` and runs on both pull requests and pushes to `main`.
