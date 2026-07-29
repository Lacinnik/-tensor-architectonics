from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_POLICY = ROOT / "claim_policy.json"


def rmse(actual: list[float], predicted: list[float]) -> float:
    if not actual or len(actual) != len(predicted):
        raise ValueError("RMSE requires equally sized non-empty samples")
    return math.sqrt(
        sum((observed - estimate) ** 2 for observed, estimate in zip(actual, predicted))
        / len(actual)
    )


def relative_rmse_improvement(
    actual: list[float],
    candidate: list[float],
    baseline: list[float],
) -> float:
    baseline_rmse = rmse(actual, baseline)
    candidate_rmse = rmse(actual, candidate)
    if baseline_rmse == 0:
        return 0.0 if candidate_rmse == 0 else -1.0
    return (baseline_rmse - candidate_rmse) / baseline_rmse


def percentile(values: list[float], probability: float) -> float:
    if not values or not 0 <= probability <= 1:
        raise ValueError("percentile requires values and probability in [0, 1]")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def bootstrap_improvements(
    actual: list[float],
    candidate: list[float],
    baseline: list[float],
    *,
    replicates: int,
    seed: int,
) -> list[float]:
    if (
        not actual
        or len(actual) != len(candidate)
        or len(actual) != len(baseline)
    ):
        raise ValueError("bootstrap requires equally sized non-empty samples")
    if replicates < 1000:
        raise ValueError("bootstrap_replicates must be at least 1000")
    rng = random.Random(seed)
    count = len(actual)
    distribution: list[float] = []
    for _ in range(replicates):
        indices = [rng.randrange(count) for _ in range(count)]
        distribution.append(
            relative_rmse_improvement(
                [actual[index] for index in indices],
                [candidate[index] for index in indices],
                [baseline[index] for index in indices],
            )
        )
    return distribution


def leave_one_event_out_improvements(
    actual: list[float],
    candidate: list[float],
    baseline: list[float],
) -> list[float]:
    if len(actual) < 2:
        raise ValueError("leave-one-event-out analysis requires at least two events")
    return [
        relative_rmse_improvement(
            [value for index, value in enumerate(actual) if index != omitted],
            [value for index, value in enumerate(candidate) if index != omitted],
            [value for index, value in enumerate(baseline) if index != omitted],
        )
        for omitted in range(len(actual))
    ]


def validate_policy(policy: dict[str, Any]) -> None:
    required = {
        "policy_id",
        "policy_version",
        "analysis_kind",
        "primary_baseline",
        "secondary_baselines",
        "noninferiority_margin_rmse",
        "minimum_noninferiority_probability",
        "minimum_superiority_improvement",
        "minimum_superiority_probability",
        "bootstrap_replicates",
        "bootstrap_seed",
        "severity_thresholds",
        "scope_status_prefix",
    }
    missing = sorted(required - policy.keys())
    if missing:
        raise ValueError(f"claim policy missing required keys: {missing}")
    for name in (
        "noninferiority_margin_rmse",
        "minimum_noninferiority_probability",
        "minimum_superiority_improvement",
        "minimum_superiority_probability",
    ):
        value = policy[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 < value < 1
        ):
            raise ValueError(f"{name} must be in (0, 1)")
    if (
        isinstance(policy["bootstrap_replicates"], bool)
        or not isinstance(policy["bootstrap_replicates"], int)
        or policy["bootstrap_replicates"] < 1000
    ):
        raise ValueError("bootstrap_replicates must be an integer of at least 1000")
    if (
        isinstance(policy["bootstrap_seed"], bool)
        or not isinstance(policy["bootstrap_seed"], int)
    ):
        raise ValueError("bootstrap_seed must be an integer")
    primary = policy["primary_baseline"]
    secondary = policy["secondary_baselines"]
    if (
        not isinstance(primary, str)
        or not primary
        or not isinstance(secondary, list)
        or any(not isinstance(item, str) or not item for item in secondary)
        or primary in secondary
        or len(secondary) != len(set(secondary))
    ):
        raise ValueError("primary and secondary baselines must be unique names")
    thresholds = policy["severity_thresholds"]
    if (
        not isinstance(thresholds, dict)
        or not isinstance(thresholds.get("severe_max_symh"), (int, float))
        or not isinstance(thresholds.get("moderate_max_symh"), (int, float))
        or thresholds["severe_max_symh"] >= thresholds["moderate_max_symh"]
    ):
        raise ValueError("invalid severity_thresholds")
    prefixes = policy["scope_status_prefix"]
    if (
        not isinstance(prefixes, dict)
        or set(prefixes) != {"in-domain", "transport"}
        or any(not isinstance(value, str) for value in prefixes.values())
    ):
        raise ValueError("scope_status_prefix must define in-domain and transport")


def extract_predictions(
    gate_metrics: dict[str, Any],
    baselines: list[str],
) -> tuple[list[str], list[float], list[float], dict[str, list[float]]]:
    rows = gate_metrics.get("validation_predictions")
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError("gate metrics must contain at least two validation predictions")
    event_ids: list[str] = []
    actual: list[float] = []
    candidate: list[float] = []
    controls = {baseline: [] for baseline in baselines}
    for row in rows:
        try:
            event_ids.append(str(row["event_id"]))
            actual.append(float(row["observed_SYM_H_min"]))
            candidate.append(float(row["EAGC_prediction"]))
            for baseline in baselines:
                controls[baseline].append(float(row[f"{baseline}_prediction"]))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid validation prediction row") from error
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("validation event identifiers must be unique")
    return event_ids, actual, candidate, controls


def comparison_metrics(
    event_ids: list[str],
    actual: list[float],
    candidate: list[float],
    baseline: list[float],
    policy: dict[str, Any],
) -> dict[str, Any]:
    distribution = bootstrap_improvements(
        actual,
        candidate,
        baseline,
        replicates=int(policy["bootstrap_replicates"]),
        seed=int(policy["bootstrap_seed"]),
    )
    omissions = leave_one_event_out_improvements(actual, candidate, baseline)
    worst_index = min(range(len(omissions)), key=omissions.__getitem__)
    confidence = float(policy["minimum_noninferiority_probability"])
    margin = float(policy["noninferiority_margin_rmse"])
    point_improvement = relative_rmse_improvement(actual, candidate, baseline)
    return {
        "n_events": len(actual),
        "candidate_rmse": rmse(actual, candidate),
        "baseline_rmse": rmse(actual, baseline),
        "rmse_improvement": point_improvement,
        "probability_of_improvement": (
            sum(value > 0 for value in distribution) / len(distribution)
        ),
        "probability_of_noninferiority": (
            sum(value > -margin for value in distribution) / len(distribution)
        ),
        "one_sided_noninferiority_lower_bound": percentile(
            distribution, 1 - confidence
        ),
        "central_90_percent_interval": [
            percentile(distribution, 0.05),
            percentile(distribution, 0.95),
        ],
        "minimum_leave_one_event_out_improvement": omissions[worst_index],
        "worst_omitted_event": event_ids[worst_index],
        "positive_leave_one_event_out_runs": sum(value > 0 for value in omissions),
        "total_leave_one_event_out_runs": len(omissions),
    }


def severity_metrics(
    actual: list[float],
    candidate: list[float],
    baseline: list[float],
    policy: dict[str, Any],
) -> dict[str, Any]:
    severe = float(policy["severity_thresholds"]["severe_max_symh"])
    moderate = float(policy["severity_thresholds"]["moderate_max_symh"])
    definitions = {
        "severe": lambda value: value <= severe,
        "moderate": lambda value: severe < value <= moderate,
        "mild": lambda value: value > moderate,
    }
    result: dict[str, Any] = {}
    for name, predicate in definitions.items():
        indices = [index for index, value in enumerate(actual) if predicate(value)]
        if not indices:
            result[name] = {"n_events": 0}
            continue
        observed = [actual[index] for index in indices]
        estimates = [candidate[index] for index in indices]
        controls = [baseline[index] for index in indices]
        result[name] = {
            "n_events": len(indices),
            "candidate_rmse": rmse(observed, estimates),
            "baseline_rmse": rmse(observed, controls),
            "rmse_improvement": relative_rmse_improvement(
                observed, estimates, controls
            ),
        }
    return result


def adjudicate(
    gate_metrics: dict[str, Any],
    policy: dict[str, Any],
    *,
    scope: str,
) -> dict[str, Any]:
    validate_policy(policy)
    if scope not in policy["scope_status_prefix"]:
        raise ValueError(f"unsupported scope: {scope}")
    baselines = [
        policy["primary_baseline"],
        *policy["secondary_baselines"],
    ]
    event_ids, actual, candidate, controls = extract_predictions(
        gate_metrics, baselines
    )
    primary_name = policy["primary_baseline"]
    primary = comparison_metrics(
        event_ids, actual, candidate, controls[primary_name], policy
    )
    margin = float(policy["noninferiority_margin_rmse"])
    noninferiority_pass = (
        primary["rmse_improvement"] > -margin
        and primary["probability_of_noninferiority"]
        >= float(policy["minimum_noninferiority_probability"])
        and primary["minimum_leave_one_event_out_improvement"] > -margin
    )
    superiority_pass = (
        primary["rmse_improvement"]
        >= float(policy["minimum_superiority_improvement"])
        and primary["probability_of_improvement"]
        >= float(policy["minimum_superiority_probability"])
        and primary["minimum_leave_one_event_out_improvement"] >= 0
    )
    prefix = policy["scope_status_prefix"][scope]
    if superiority_pass:
        decision = f"{prefix}PASS-SUPERIOR"
    elif noninferiority_pass:
        decision = f"{prefix}PASS-NONINFERIOR"
    else:
        decision = f"{prefix}REJECT"
    secondary = {
        name: comparison_metrics(
            event_ids, actual, candidate, controls[name], policy
        )
        for name in policy["secondary_baselines"]
    }
    return {
        "decision": decision,
        "scope": scope,
        "analysis_kind": policy["analysis_kind"],
        "policy_id": policy["policy_id"],
        "policy_version": policy["policy_version"],
        "legacy_gate_decision": gate_metrics.get("decision"),
        "primary_baseline": primary_name,
        "noninferiority_margin_rmse": margin,
        "noninferiority_gate_pass": noninferiority_pass,
        "superiority_gate_pass": superiority_pass,
        "primary_comparison": primary,
        "secondary_comparisons": secondary,
        "severity_strata_vs_primary": severity_metrics(
            actual, candidate, controls[primary_name], policy
        ),
        "interpretation": policy.get("interpretation"),
        "limitations": policy.get("limitations"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Adjudicate frozen EAGC-012 predictions without refitting models."
    )
    parser.add_argument("gate_metrics", type=Path)
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY,
        help="claim adjudication policy (default: tools/eagc012/claim_policy.json)",
    )
    parser.add_argument(
        "--scope",
        choices=("in-domain", "transport"),
        required=True,
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gate_metrics = json.loads(args.gate_metrics.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    result = adjudicate(gate_metrics, policy, scope=args.scope)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
