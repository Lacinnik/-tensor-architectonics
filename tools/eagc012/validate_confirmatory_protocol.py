#!/usr/bin/env python3
"""Fail-closed semantic, artifact, and Git-anchor validation for ICME v1.1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from confirmatory_common import (
    BOOTSTRAP_PATH,
    MODEL_PATH,
    PROTOCOL_ID,
    PROTOCOL_PATH,
    PROTOCOL_VERSION,
    REGISTRY_PATH,
    repository_root,
    sha256_file,
    verify_protocol_anchor,
)


EXPECTED_PROTOCOL_SHA256 = "a423e8274f1149d3e3e0997d09fc87bad433a1cb93208741e5fda24ea7cc6bc9"
EXPECTED_REGISTRY_SHA256 = "11e8fd28c9e84e4a493f416741af63368b858e826e49f9147098d228ffdb3b92"
EXPECTED_V1_PROTOCOL_SHA256 = "7c2251d3fb3374c28707a1c5466b8142293360c158bf6557ce5c71f309fa4c79"
EXPECTED_MODEL_SHA256 = "948b1ee4d176035e47f15e7708c9795dfc482fa739c6533a4b894c948c9fc5bd"
EXPECTED_BOOTSTRAP_SHA256 = "f5c51d0a02b7ca4d17ae6f703c2f84d7b8a99b03190bdc0ba5702b91efb28027"
EXPECTED_PRECEDENCE = [
    "HOLD",
    "PASS-SUPERIOR",
    "PASS-NONINFERIOR",
    "REJECT",
]
EXPECTED_NONINFERIOR = [
    "All 20 frozen events are SCORABLE.",
    "Point relative improvement is strictly greater than -0.05.",
    "The frozen-index bootstrap fraction with relative improvement strictly greater than -0.05 is at least 0.90.",
    "Every leave-one-event-out relative improvement is strictly greater than -0.05.",
]
EXPECTED_SUPERIOR = [
    "Every PASS-NONINFERIOR condition passes.",
    "Point relative improvement is at least 0.05.",
    "The frozen-index bootstrap fraction with relative improvement strictly greater than 0 is at least 0.90.",
    "Every leave-one-event-out relative improvement is strictly greater than 0.",
]
EXPECTED_REJECT = (
    "All 20 frozen events are SCORABLE and at least one PASS-NONINFERIOR "
    "condition fails."
)
EXPECTED_HOLD = (
    "Any incomplete cohort, non-SCORABLE event, zero Newell RMSE, missing "
    "provenance, hash mismatch, chronology failure, catalog revision, "
    "unauthorized target access, or other invariant violation."
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_protocol(protocol: dict[str, Any]) -> None:
    require(protocol.get("protocol_id") == PROTOCOL_ID, "unexpected protocol_id")
    require(
        protocol.get("protocol_version") == PROTOCOL_VERSION,
        "unexpected protocol_version",
    )
    require(protocol.get("status") == "FROZEN-PRE-TARGET", "protocol status")
    require(
        protocol.get("supersedes")
        == {
            "protocol_version": "1.0.0-prospective",
            "status": "SUPERSEDED-BEFORE-ACCRUAL",
            "freeze_commit": "2203bcd4513b538aec66062083a882f88f9ebf97",
        },
        "v1 supersession boundary changed",
    )

    scope = protocol["claim_scope"]
    require(scope["primary_baseline"] == "Newell", "primary baseline changed")
    require(scope["transport_exclusions"] == ["SIR"], "SIR exclusion changed")
    require(
        scope["secondary_descriptive_baselines"]
        == ["V_Bs", "I_Q", "Burton_OBrien_McPherron"],
        "secondary baseline policy changed",
    )

    freeze = protocol["freeze"]
    require(freeze["anchor_kind"] == "introducing_git_commit", "anchor kind")
    require(freeze["repository"] == "Lacinnik/-tensor-architectonics", "repository")
    require(freeze["path"] == PROTOCOL_PATH.as_posix(), "protocol path")
    require(
        "Current protocol bytes MUST equal" in freeze["resolution_rule"],
        "anchor byte equality missing",
    )
    require(
        "strictly later" in freeze["prospective_boundary"],
        "prospective time boundary changed",
    )
    require(
        "new protocol version" in freeze["amendment_policy"],
        "amendment policy changed",
    )

    states = protocol["state_machine"]
    require("Any broken invariant -> HOLD" in states["transitions"], "HOLD transition")
    require("No accrued event" in states["rollback"], "rollback boundary")

    cohort = protocol["cohort"]
    require(cohort["planned_events"] == 20, "cohort size changed")
    require(cohort["replacement_policy"] == "NONE", "replacement policy")
    require(cohort["initial_state"] == "NOT_STARTED", "initial accrual state")
    require(
        cohort["ordering"]
        == ["icme_start_time ascending", "icmecat_id ascending"],
        "cohort ordering changed",
    )
    require(
        "Append selections only" in cohort["accrual_policy"],
        "append-only accrual missing",
    )
    require(
        "HOLD-CATALOG-REVISION" in cohort["catalog_revision_policy"],
        "catalog revision guard missing",
    )
    require(cohort["eligibility"]["sc_insitu"] == "Wind", "spacecraft changed")
    require(
        cohort["eligibility"]["minimum_minutes_after_cutoff"] == 720,
        "target window minimum changed",
    )

    selector = protocol["sources"]["selector"]
    require(selector["minimum_version"] == "2.3", "catalog minimum version")
    require(
        selector["allowlisted_columns"]
        == ["icmecat_id", "sc_insitu", "icme_start_time", "mo_end_time"],
        "selector allowlist changed",
    )
    require(
        set(selector["target_columns_forbidden_in_manifest"]) == {"Dst", "SYM-H"},
        "target ban changed",
    )
    require(
        "ascending order" in selector["discovery_policy"],
        "snapshot discovery order missing",
    )
    target = protocol["sources"]["predictors_and_target"]
    require(target["dataset_id"] == "OMNI_HRO_1MIN", "target dataset changed")
    require(target["target_field"] == "SYM-H", "target field changed")
    require(
        "two ordered commits" in target["access_boundary"],
        "two-commit target guard missing",
    )

    window = protocol["window"]
    require(window["semantics"] == "half-open [start,end)", "window semantics")
    require(window["cutoff_minutes_after_start"] == 720, "cutoff changed")
    require(window["target_window"] == "[cutoff, mo_end_time)", "target window")

    model = protocol["model"]
    require(model["fit_policy"] == "NEVER_REFIT", "model refit guard")
    require(
        model["source_commit"]
        == "2da7de6df1ca0d3ff2a1a89576f078c97d389298",
        "model source commit changed",
    )
    require(model["artifact_path"] == MODEL_PATH.as_posix(), "model path")
    require(model["artifact_sha256"] == EXPECTED_MODEL_SHA256, "model hash")
    require(model["eagc_alpha"] == 10.0, "ridge alpha")
    require(
        model["eagc_features"]
        == ["pressure_peak", "log_Newell", "pressure_recent", "south_hours"],
        "model features changed",
    )

    comparison = protocol["comparison"]
    require(
        comparison["relative_improvement_formula"]
        == "(RMSE_Newell - RMSE_EAGC) / RMSE_Newell",
        "relative improvement formula changed",
    )
    require(comparison["zero_baseline_rmse_policy"] == "HOLD", "zero RMSE policy")
    require(comparison["bootstrap_replicates"] == 10000, "bootstrap count")
    require(comparison["bootstrap_sample_size"] == 20, "bootstrap sample size")
    require(
        comparison["bootstrap_indices_sha256"] == EXPECTED_BOOTSTRAP_SHA256,
        "bootstrap artifact hash",
    )
    require(
        comparison["noninferiority_margin_relative_rmse"] == -0.05,
        "noninferiority margin",
    )
    require(
        comparison["superiority_margin_relative_rmse"] == 0.05,
        "superiority margin",
    )
    require(comparison["minimum_bootstrap_probability"] == 0.9, "probability")

    decision = protocol["decision"]
    require(decision["PASS-NONINFERIOR"] == EXPECTED_NONINFERIOR, "NI decision")
    require(decision["PASS-SUPERIOR"] == EXPECTED_SUPERIOR, "superior decision")
    require(decision["REJECT"] == EXPECTED_REJECT, "REJECT decision")
    require(decision["HOLD"] == EXPECTED_HOLD, "HOLD decision")
    require(decision["precedence"] == EXPECTED_PRECEDENCE, "decision precedence")

    quality = protocol["data_quality"]
    require(
        quality["required_prefix_fields"]
        == ["by", "bz", "speed", "pressure", "symh"],
        "quality fields changed",
    )
    require(quality["minimum_prefix_coverage"] == 0.75, "prefix coverage")
    require(quality["minimum_target_symh_coverage"] == 0.9, "target coverage")
    require(quality["maximum_gap_minutes"] == 15, "gap threshold")
    require(
        protocol["reproducibility"]["python"] == "3.12.14",
        "Python runtime changed",
    )


def validate_registry(registry: dict[str, Any]) -> None:
    active = registry["active_protocol"]
    require(active["protocol_id"] == PROTOCOL_ID, "registry protocol_id")
    require(active["protocol_version"] == PROTOCOL_VERSION, "registry version")
    require(active["path"] == PROTOCOL_PATH.as_posix(), "registry active path")
    require(active["status"] == "FROZEN-PRE-TARGET", "registry active status")
    versions = {item["protocol_version"]: item for item in registry["versions"]}
    require(
        versions["1.0.0-prospective"]["status"]
        == "SUPERSEDED-BEFORE-ACCRUAL",
        "v1 registry status",
    )
    require(
        versions[PROTOCOL_VERSION]["accrual_state"] == "NOT_STARTED",
        "v1.1 accrual state",
    )


def validate_artifacts(root: Path, protocol: dict[str, Any]) -> None:
    require(sha256_file(root / PROTOCOL_PATH) == EXPECTED_PROTOCOL_SHA256, "protocol bytes")
    require(sha256_file(root / REGISTRY_PATH) == EXPECTED_REGISTRY_SHA256, "registry bytes")
    require(
        sha256_file(root / "tools/eagc012/confirmatory_icme_protocol.json")
        == EXPECTED_V1_PROTOCOL_SHA256,
        "v1 frozen protocol changed",
    )
    require(sha256_file(root / MODEL_PATH) == EXPECTED_MODEL_SHA256, "model artifact")
    require(
        sha256_file(root / BOOTSTRAP_PATH) == EXPECTED_BOOTSTRAP_SHA256,
        "bootstrap artifact",
    )
    model = json.loads((root / MODEL_PATH).read_text(encoding="utf-8"))
    require(model["status"] == "FROZEN-PRE-TARGET", "model status")
    require(model["fit_policy"].startswith("Parameters are immutable"), "model fit policy")
    require(model["training_cohort"]["event_count"] == 80, "training event count")
    require(len(model["training_cohort"]["source_files"]) == 66, "training source hashes")
    for path, expected in protocol["reproducibility"]["implementation_sha256"].items():
        require(sha256_file(root / path) == expected, f"implementation drift: {path}")


def load_and_validate(root: Path, *, verify_git: bool = True) -> dict[str, Any]:
    protocol = json.loads((root / PROTOCOL_PATH).read_text(encoding="utf-8"))
    registry = json.loads((root / REGISTRY_PATH).read_text(encoding="utf-8"))
    validate_protocol(protocol)
    validate_registry(registry)
    validate_artifacts(root, protocol)
    if verify_git:
        anchor = verify_protocol_anchor(root)
        require(anchor["protocol_sha256"] == EXPECTED_PROTOCOL_SHA256, "Git anchor hash")
    return protocol


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-git-anchor", action="store_true")
    args = parser.parse_args()
    root = repository_root(Path(__file__).parent)
    protocol = load_and_validate(root, verify_git=not args.no_git_anchor)
    print(f"READY-TO-ACCRUE {protocol['protocol_id']} {protocol['protocol_version']}")


if __name__ == "__main__":
    main()
