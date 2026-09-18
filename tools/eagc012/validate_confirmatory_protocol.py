#!/usr/bin/env python3
"""Fail-closed validation for the EAGC-012 prospective ICME protocol."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_PROTOCOL_ID = "TZAR-RESEARCH-EAGC-012-CONFIRMATORY-ICME"
EXPECTED_FEATURES = [
    "pressure_peak",
    "log_Newell",
    "pressure_recent",
    "south_hours",
]
EXPECTED_SECONDARY = ["V_Bs", "I_Q", "Burton_OBrien_McPherron"]
FORBIDDEN_TRANSPORT = "SIR"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_keys(value: dict[str, Any], keys: set[str], context: str) -> None:
    missing = sorted(keys - value.keys())
    require(not missing, f"{context} missing: {', '.join(missing)}")


def load_protocol(path: Path) -> dict[str, Any]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(protocol, dict), "protocol must be a JSON object")
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    require_keys(
        protocol,
        {
            "protocol_id",
            "protocol_version",
            "status",
            "claim_scope",
            "freeze",
            "cohort",
            "sources",
            "window",
            "model",
            "comparison",
            "decision",
            "data_quality",
            "reproducibility",
        },
        "protocol",
    )
    require(protocol["protocol_id"] == EXPECTED_PROTOCOL_ID, "unexpected protocol_id")
    require(protocol["status"] == "FROZEN-PRE-TARGET", "protocol must be frozen pre-target")

    scope = protocol["claim_scope"]
    require(FORBIDDEN_TRANSPORT in scope["transport_exclusions"], "SIR must be excluded")
    forbidden = " ".join(scope["forbidden_inferences"])
    require("PASS-SUPERIOR" in forbidden, "superiority boundary must be explicit")
    require("new cohort" in forbidden, "superiority must require new-cohort evidence")

    freeze = protocol["freeze"]
    require(freeze["anchor_kind"] == "introducing_git_commit", "freeze must use Git commit")
    require("strictly later" in freeze["prospective_boundary"], "boundary must be prospective")
    require("new protocol version" in freeze["amendment_policy"], "amendments must restart accrual")

    cohort = protocol["cohort"]
    require(cohort["planned_events"] == 20, "cohort size must remain 20")
    require(cohort["replacement_policy"] == "NONE", "event replacement must be forbidden")
    require(cohort["accrual_state"] == "NOT_STARTED", "preregistration must contain no accrued events")
    require("before any target source is queried" in cohort["manifest_freeze_rule"], "manifest must precede targets")
    require(cohort["eligibility"]["sc_insitu"] == "Wind", "cohort must be near-Earth Wind")
    require(cohort["eligibility"]["minimum_minutes_after_cutoff"] == 720, "target window minimum changed")

    selector = protocol["sources"]["selector"]
    require("{major}{minor}" in selector["machine_url_pattern"], "selector URL must be versioned")
    require("highest officially linked ICMECAT version" in selector["version_policy"], "catalog version policy missing")
    require(selector["allowlisted_columns"] == [
        "icmecat_id", "sc_insitu", "icme_start_time", "mo_end_time"
    ], "selector projection changed")
    require(set(selector["target_columns_forbidden_during_accrual"]) == {"Dst", "SYM-H"}, "target ban changed")

    target = protocol["sources"]["predictors_and_target"]
    require(target["dataset_id"] == "OMNI_HRO_1MIN", "unexpected target dataset")
    require(target["target_field"] == "SYM-H", "unexpected target field")
    require("until the complete target-blind cohort manifest is frozen" in target["access_boundary"], "target access guard missing")

    window = protocol["window"]
    require(window["cutoff_minutes_after_start"] == 720, "cutoff must remain 12 hours")
    require(window["semantics"] == "half-open [start,end)", "window semantics changed")

    model = protocol["model"]
    require(model["kind"] == "standardized_ridge", "model kind changed")
    require(model["alpha"] == 10.0, "ridge alpha changed")
    require(model["features"] == EXPECTED_FEATURES, "feature set or order changed")
    require(len(model["source_commit"]) == 40, "model source_commit must be a full SHA")
    require("Confirmatory target values must never affect fitting" in model["fit_policy"], "fit leakage guard missing")

    comparison = protocol["comparison"]
    require(comparison["primary_baseline"] == "Newell", "primary baseline changed")
    require(comparison["secondary_descriptive_baselines"] == EXPECTED_SECONDARY, "secondary baseline policy changed")
    require(comparison["bootstrap_replicates"] == 10000, "bootstrap count changed")
    require(comparison["bootstrap_seed"] == 12012, "bootstrap seed changed")
    require(comparison["noninferiority_margin_relative_rmse"] == -0.05, "noninferiority margin changed")
    require(comparison["superiority_margin_relative_rmse"] == 0.05, "superiority margin changed")
    require(comparison["minimum_bootstrap_probability"] == 0.9, "bootstrap threshold changed")

    decision = protocol["decision"]
    require_keys(decision, {"PASS-NONINFERIOR", "PASS-SUPERIOR", "REJECT", "HOLD", "precedence"}, "decision")
    require(decision["precedence"][0] == "HOLD", "HOLD must fail closed")
    superior = " ".join(decision["PASS-SUPERIOR"])
    require("at least 0.05" in superior, "superiority point margin missing")
    require("greater than 0" in superior, "superiority resampling guards missing")

    quality = protocol["data_quality"]
    require(quality["failure_policy"].startswith("Fail closed to HOLD"), "quality must fail closed")
    require(quality["minimum_prefix_coverage"] == 0.75, "prefix coverage changed")
    require(quality["minimum_target_symh_coverage"] == 0.9, "target coverage changed")
    require(quality["maximum_gap_minutes"] == 15, "gap limit changed")

    reproducibility = protocol["reproducibility"]
    require(reproducibility["python"] == "3.12", "Python version must be fixed")
    require(len(reproducibility["required_artifacts"]) >= 6, "reproducibility artifact plan incomplete")
    require("manifest commit predates target retrieval" in reproducibility["runner_guard"], "runner chronology guard missing")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path(__file__).with_name("confirmatory_icme_protocol.json"),
    )
    args = parser.parse_args()
    protocol = load_protocol(args.path)
    print(f"READY-TO-ACCRUE {protocol['protocol_id']} {protocol['protocol_version']}")


if __name__ == "__main__":
    main()
