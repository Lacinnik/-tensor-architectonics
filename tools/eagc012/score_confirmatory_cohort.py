#!/usr/bin/env python3
"""Score the frozen prospective EAGC-012 ICME cohort without refitting."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from confirmatory_common import (
    AUTHORIZATION_PATH,
    BOOTSTRAP_PATH,
    MANIFEST_PATH,
    MODEL_PATH,
    OMNI_BASE,
    PROTOCOL_ID,
    PROTOCOL_PATH,
    PROTOCOL_VERSION,
    months_for,
    repository_root,
    require_ancestor,
    require_exact_committed_file,
    sha256_file,
    utc,
    validate_authorization_document,
    validate_manifest,
    validate_parent_manifest_evidence,
    validate_source_receipts,
    verify_protocol_anchor,
)


def load_bootstrap_indices(path: Path, replicates: int, size: int) -> list[bytes]:
    raw = path.read_bytes()
    if len(raw) != replicates * size:
        raise ValueError("bootstrap index artifact has wrong length")
    rows = [raw[offset : offset + size] for offset in range(0, len(raw), size)]
    if any(index >= size for row in rows for index in row):
        raise ValueError("bootstrap index outside cohort")
    return rows


def predict(model: dict[str, Any], item: dict[str, Any]) -> float:
    from run_gate import predict_ridge, predict_univariate

    if model["kind"] == "standardized_ridge":
        return predict_ridge(model, item)
    if model["kind"] == "log_linear":
        return predict_univariate(model, item)
    raise ValueError(f"unsupported frozen model kind: {model['kind']}")


def resampled_probability(
    actual: list[float],
    candidate: list[float],
    baseline: list[float],
    indices: list[bytes],
    *,
    threshold: float,
) -> float:
    from run_gate import relative_improvement, rmse

    wins = 0
    for row in indices:
        observed = [actual[index] for index in row]
        candidate_rmse = rmse(observed, [candidate[index] for index in row])
        baseline_rmse = rmse(observed, [baseline[index] for index in row])
        if baseline_rmse == 0:
            raise ValueError("bootstrap baseline RMSE is zero")
        if relative_improvement(candidate_rmse, baseline_rmse) > threshold:
            wins += 1
    return wins / len(indices)


def leave_one_out_improvements(
    actual: list[float], candidate: list[float], baseline: list[float]
) -> list[float]:
    from run_gate import relative_improvement, rmse

    values: list[float] = []
    for omitted in range(len(actual)):
        keep = [index for index in range(len(actual)) if index != omitted]
        candidate_rmse = rmse(
            [actual[index] for index in keep],
            [candidate[index] for index in keep],
        )
        baseline_rmse = rmse(
            [actual[index] for index in keep],
            [baseline[index] for index in keep],
        )
        if baseline_rmse == 0:
            raise ValueError("leave-one-out baseline RMSE is zero")
        values.append(relative_improvement(candidate_rmse, baseline_rmse))
    return values


def hold(reasons: list[str]) -> dict[str, Any]:
    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "decision": "HOLD",
        "hold_reasons": reasons,
    }


def adjudicate_metrics(
    *,
    point: float,
    probability_noninferior: float,
    probability_superior: float,
    omitted: list[float],
) -> str:
    noninferior = (
        point > -0.05
        and probability_noninferior >= 0.90
        and all(value > -0.05 for value in omitted)
    )
    superior = (
        noninferior
        and point >= 0.05
        and probability_superior >= 0.90
        and all(value > 0.0 for value in omitted)
    )
    if superior:
        return "PASS-SUPERIOR"
    if noninferior:
        return "PASS-NONINFERIOR"
    return "REJECT"


def score_summary(
    summary: dict[str, Any],
    manifest: dict[str, Any],
    authorization: dict[str, Any],
    model_artifact: dict[str, Any],
    indices: list[bytes],
) -> dict[str, Any]:
    from run_gate import relative_improvement, rmse

    reasons: list[str] = []
    for label, value in (
        ("summary", summary),
        ("manifest", manifest),
        ("authorization", authorization),
    ):
        if value.get("protocol_id") != PROTOCOL_ID:
            reasons.append(f"{label} protocol_id mismatch")
        if value.get("protocol_version") != PROTOCOL_VERSION:
            reasons.append(f"{label} protocol_version mismatch")
    if manifest.get("state") != "MANIFEST-CANDIDATE":
        reasons.append("manifest is not frozen candidate")
    if manifest.get("selected_event_count") != 20:
        reasons.append("manifest does not contain 20 events")
    if summary.get("manifest_sha256") != authorization.get("manifest", {}).get(
        "sha256"
    ):
        reasons.append("summary manifest hash mismatch")
    if summary.get("authorization_sha256") is None:
        reasons.append("summary lacks authorization hash")
    sources = summary.get("source_files")
    if not isinstance(sources, dict) or not sources:
        reasons.append("target source provenance is incomplete")
    elif any(
        not item.get("sha256") or not item.get("retrieved_at") or not item.get("url")
        for item in sources.values()
    ):
        reasons.append("target source receipt is incomplete")
    elif any(
        item.get("url") != f"{OMNI_BASE}/omni_min{month}.asc"
        for month, item in sources.items()
    ):
        reasons.append("target source URL is not canonical")

    expected_ids = [item["icmecat_id"] for item in manifest.get("selected_events", [])]
    events = summary.get("events")
    if not isinstance(events, list) or [item.get("event_id") for item in events] != expected_ids:
        reasons.append("event order or identity differs from frozen manifest")
    elif any(
        item.get("window_start") != frozen.get("icme_start_time")
        or item.get("forecast_cutoff") != frozen.get("cutoff")
        or item.get("window_end_exclusive") != frozen.get("mo_end_time")
        or item.get("source_months")
        != months_for(
            utc(frozen["icme_start_time"]), utc(frozen["mo_end_time"])
        )
        for item, frozen in zip(events, manifest.get("selected_events", []))
    ):
        reasons.append("event windows differ from frozen manifest")
    if reasons:
        return hold(reasons)

    assert isinstance(events, list)
    required_features = {
        "pressure_peak",
        "log_Newell",
        "pressure_recent",
        "south_hours",
        "Newell",
        "V_Bs",
        "I_Q",
        "Burton_OBrien_McPherron",
    }
    for event in events:
        if event.get("quality_status") != "SCORABLE":
            reasons.append(f"{event['event_id']} is not SCORABLE")
        if event.get("SYM_H_min") is None:
            reasons.append(f"{event['event_id']} lacks target")
        missing = sorted(name for name in required_features if event.get(name) is None)
        if missing:
            reasons.append(f"{event['event_id']} lacks: {', '.join(missing)}")
        numeric = [event.get("SYM_H_min"), *(event.get(name) for name in required_features)]
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in numeric
        ):
            reasons.append(f"{event['event_id']} contains non-finite numeric evidence")
    if reasons:
        return hold(reasons)

    models = model_artifact["models"]
    actual = [float(item["SYM_H_min"]) for item in events]
    predictions = {
        name: [predict(model, item) for item in events]
        for name, model in models.items()
    }
    baseline = predictions["Newell"]
    candidate = predictions["EAGC"]
    candidate_rmse = rmse(actual, candidate)
    baseline_rmse = rmse(actual, baseline)
    if baseline_rmse == 0:
        return hold(["primary baseline RMSE is zero"])
    point = relative_improvement(candidate_rmse, baseline_rmse)
    try:
        probability_noninferior = resampled_probability(
            actual, candidate, baseline, indices, threshold=-0.05
        )
        probability_superior = resampled_probability(
            actual, candidate, baseline, indices, threshold=0.0
        )
        omitted = leave_one_out_improvements(actual, candidate, baseline)
    except ValueError as error:
        return hold([str(error)])

    decision = adjudicate_metrics(
        point=point,
        probability_noninferior=probability_noninferior,
        probability_superior=probability_superior,
        omitted=omitted,
    )
    secondary: dict[str, Any] = {}
    for name in ("V_Bs", "I_Q", "Burton_OBrien_McPherron"):
        control_rmse = rmse(actual, predictions[name])
        secondary[name] = {
            "rmse": control_rmse,
            "relative_improvement": (
                relative_improvement(candidate_rmse, control_rmse)
                if control_rmse
                else None
            ),
        }
    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "decision": decision,
        "hold_reasons": [],
        "primary_baseline": "Newell",
        "n_events": 20,
        "candidate_rmse": candidate_rmse,
        "baseline_rmse": baseline_rmse,
        "relative_improvement": point,
        "bootstrap_probability_noninferior": probability_noninferior,
        "bootstrap_probability_superior": probability_superior,
        "minimum_leave_one_out_improvement": min(omitted),
        "secondary_descriptive": secondary,
        "predictions": [
            {
                "event_id": event["event_id"],
                "observed_SYM_H_min": actual[index],
                **{
                    f"{name}_prediction": values[index]
                    for name, values in predictions.items()
                },
            }
            for index, event in enumerate(events)
        ],
    }


def execute(args: argparse.Namespace) -> dict[str, Any]:
    root = repository_root(Path(__file__).parent)
    from validate_confirmatory_protocol import load_and_validate

    protocol = load_and_validate(root)
    protocol_anchor = verify_protocol_anchor(root)
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    authorization_path = (
        args.authorization
        if args.authorization.is_absolute()
        else root / args.authorization
    )
    manifest_evidence = require_exact_committed_file(
        root, manifest_path.relative_to(root)
    )
    authorization_evidence = require_exact_committed_file(
        root, authorization_path.relative_to(root)
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    validate_manifest(manifest, protocol_anchor, require_complete=True)
    require_ancestor(root, protocol_anchor["commit"], manifest_evidence["commit"])
    validate_parent_manifest_evidence(root, manifest, manifest_evidence)
    validate_authorization_document(
        authorization,
        manifest_evidence=manifest_evidence,
        protocol_anchor=protocol_anchor,
    )
    require_ancestor(root, manifest_evidence["commit"], authorization_evidence["commit"])

    model_path = root / MODEL_PATH
    bootstrap_path = root / BOOTSTRAP_PATH
    if sha256_file(model_path) != protocol["model"]["artifact_sha256"]:
        raise ValueError("frozen model artifact hash mismatch")
    if sha256_file(bootstrap_path) != protocol["comparison"]["bootstrap_indices_sha256"]:
        raise ValueError("bootstrap index artifact hash mismatch")
    model = json.loads(model_path.read_text(encoding="utf-8"))
    indices = load_bootstrap_indices(bootstrap_path, 10000, 20)
    summary_path = args.summary if args.summary.is_absolute() else root / args.summary
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("manifest_commit") != manifest_evidence["commit"]:
        raise ValueError("summary manifest commit mismatch")
    if summary.get("authorization_commit") != authorization_evidence["commit"]:
        raise ValueError("summary authorization commit mismatch")
    if summary.get("manifest_sha256") != manifest_evidence["sha256"]:
        raise ValueError("summary manifest hash mismatch")
    if summary.get("authorization_sha256") != authorization_evidence["sha256"]:
        raise ValueError("summary authorization hash mismatch")
    validate_source_receipts(summary, manifest, authorization_evidence)

    raw_dir = summary_path.parent / f"{summary_path.stem}-raw"
    sources: dict[str, dict[str, Any]] = {}
    for month, receipt in summary["source_files"].items():
        path = raw_dir / f"omni_min{month}.asc"
        if not path.is_file():
            raise ValueError(f"missing target source file: {path}")
        if sha256_file(path) != receipt["sha256"] or path.stat().st_size != receipt["size_bytes"]:
            raise ValueError(f"target source file evidence mismatch: {month}")
        sources[month] = {**receipt, "path": path}
    from prepare_confirmatory_data import build_event_summaries

    recomputed_events = build_event_summaries(manifest, sources)
    if recomputed_events != summary.get("events"):
        raise ValueError("event summary does not reproduce from target source files")
    return score_summary(summary, manifest, authorization, model, indices)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--authorization", type=Path, default=AUTHORIZATION_PATH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = execute(args)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        result = hold([str(error)])
    root = repository_root(Path(__file__).parent)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(result["decision"])


if __name__ == "__main__":
    main()
