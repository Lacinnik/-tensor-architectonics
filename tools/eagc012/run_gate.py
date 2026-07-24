from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import statistics
import urllib.request
from collections import Counter
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
POLICY_PATH = ROOT / "policy.json"
OUT = Path(os.environ.get("EAGC_OUT", "artifacts/eagc012"))

# Official High Resolution OMNI 1-minute ASCII columns, zero-based.
IDX = {
    "year": 0,
    "doy": 1,
    "hour": 2,
    "minute": 3,
    "bmag": 13,
    "bz": 18,
    "speed": 21,
    "density": 25,
    "pressure": 27,
    "ae": 37,
    "al": 38,
    "symh": 41,
}
FILLS = {
    "bmag": 999.99,
    "bz": 999.99,
    "speed": 99999.9,
    "density": 999.99,
    "pressure": 99.99,
    "ae": 99999.0,
    "al": 99999.0,
    "symh": 99999.0,
}
IMPLEMENTED_BASELINES = {"V_Bs", "I_Q"}


@dataclass(frozen=True)
class Event:
    event_id: str
    sheet_tab: str
    months: tuple[str, ...]
    start: datetime
    cutoff: datetime
    end: datetime


@dataclass(frozen=True)
class Row:
    t: datetime
    bmag: float | None
    bz: float | None
    speed: float | None
    density: float | None
    pressure: float | None
    ae: float | None
    al: float | None
    symh: float | None


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "protocol_id",
        "protocol_version",
        "sensor_version",
        "dataset_id",
        "source_base",
        "required_coverage_fields",
        "gap_fields",
        "minimum_coverage",
        "maximum_gap_minutes",
        "minimum_independent_events",
        "required_baselines",
        "events",
    }
    missing = sorted(required - policy.keys())
    if missing:
        raise ValueError(f"policy missing required keys: {missing}")
    return policy


def load_events(policy: dict[str, Any]) -> list[Event]:
    events = [
        Event(
            event_id=item["event_id"],
            sheet_tab=item["sheet_tab"],
            months=tuple(item["months"]),
            start=dt(item["start"]),
            cutoff=dt(item["cutoff"]),
            end=dt(item["end"]),
        )
        for item in policy["events"]
    ]
    for event in events:
        if not event.start < event.cutoff < event.end:
            raise ValueError(f"invalid cutoff ordering for {event.event_id}")
        required_months = {
            event.start.strftime("%Y%m"),
            (event.end - timedelta(minutes=1)).strftime("%Y%m"),
        }
        if not required_months.issubset(event.months):
            raise ValueError(
                f"{event.event_id} does not list every month crossed by its window"
            )
    return events


def clean(name: str, value: str) -> float | None:
    try:
        number = float(value)
    except ValueError:
        return None
    fill = FILLS[name]
    if abs(number - fill) < 1e-6 or abs(number) >= fill:
        return None
    return number


def acquire(month: str, source_base: str, out: Path) -> tuple[Path, str]:
    filename = f"omni_min{month}.asc"
    destination = out / filename
    source_dir = os.environ.get("EAGC_SOURCE_DIR")
    if source_dir:
        source = Path(source_dir) / filename
        if not source.is_file():
            raise FileNotFoundError(source)
        if not destination.exists():
            shutil.copyfile(source, destination)
    elif not destination.exists():
        url = f"{source_base}/{filename}"
        temporary = destination.with_suffix(".asc.part")
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                with temporary.open("wb") as target:
                    shutil.copyfileobj(response, target)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return destination, f"{source_base}/{filename}"


def parse(
    path: Path, start: datetime, end: datetime
) -> tuple[list[Row], bool, int, int]:
    rows: list[Row] = []
    monotonic = True
    duplicates = 0
    malformed = 0
    previous: datetime | None = None
    seen: set[datetime] = set()
    with path.open("r", encoding="ascii", errors="strict") as source:
        for line in source:
            parts = line.split()
            if len(parts) <= max(IDX.values()):
                malformed += 1
                continue
            try:
                timestamp = datetime.strptime(
                    f"{parts[0]} {parts[1]} {parts[2]} {parts[3]}",
                    "%Y %j %H %M",
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                malformed += 1
                continue
            if not start <= timestamp < end:
                continue
            if previous is not None and timestamp <= previous:
                monotonic = False
            if timestamp in seen:
                duplicates += 1
            seen.add(timestamp)
            previous = timestamp
            rows.append(
                Row(
                    timestamp,
                    clean("bmag", parts[IDX["bmag"]]),
                    clean("bz", parts[IDX["bz"]]),
                    clean("speed", parts[IDX["speed"]]),
                    clean("density", parts[IDX["density"]]),
                    clean("pressure", parts[IDX["pressure"]]),
                    clean("ae", parts[IDX["ae"]]),
                    clean("al", parts[IDX["al"]]),
                    clean("symh", parts[IDX["symh"]]),
                )
            )
    return rows, monotonic, duplicates, malformed


def minute_grid(rows: list[Row], start: datetime, end: datetime) -> list[Row]:
    by_time = {row.t: row for row in rows}
    empty = {field.name: None for field in fields(Row) if field.name != "t"}
    grid: list[Row] = []
    timestamp = start
    while timestamp < end:
        grid.append(by_time.get(timestamp, Row(t=timestamp, **empty)))
        timestamp += timedelta(minutes=1)
    return grid


def coverage(rows: list[Row], key: str) -> float:
    return sum(getattr(row, key) is not None for row in rows) / max(1, len(rows))


def max_gap(rows: list[Row], key: str) -> int:
    run = 0
    best = 0
    for row in rows:
        if getattr(row, key) is None:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def q(value: float, low: float, high: float) -> float:
    return max(0.0, min(1.0, (value - low) / (high - low)))


def feature_vector(rows: list[Row], cutoff: datetime) -> dict[str, float | int] | None:
    prefix = [row for row in rows if row.t < cutoff]
    valid = [
        row
        for row in prefix
        if row.bz is not None and row.speed is not None and row.pressure is not None
    ]
    if not valid:
        return None
    south = [row for row in valid if row.bz < -5]
    iq = sum(
        max(0.0, -row.bz) * row.speed * math.sqrt(max(row.pressure, 0.0))
        for row in valid
    ) / len(valid)
    vb = sum(max(0.0, -row.bz) * row.speed for row in valid) / len(valid)

    candidates: list[int] = []
    for index in range(30, len(prefix)):
        before = prefix[index - 30]
        after = prefix[index]
        if None in (
            before.speed,
            after.speed,
            before.pressure,
            after.pressure,
            before.bmag,
            after.bmag,
        ):
            continue
        speed_change = after.speed - before.speed
        pressure_ratio = after.pressure / max(before.pressure, 0.1)
        field_ratio = after.bmag / max(before.bmag, 0.1)
        if speed_change >= 70 and pressure_ratio >= 1.8 and field_ratio >= 1.4:
            candidates.append(index)
    clusters: list[int] = []
    for index in candidates:
        if not clusters or index - clusters[-1] > 180:
            clusters.append(index)
    front_count = len(clusters)
    if front_count > 1:
        gaps = [
            (clusters[index] - clusters[index - 1]) / 60
            for index in range(1, front_count)
        ]
        compactness = math.exp(-statistics.median(gaps) / 18)
    else:
        compactness = 0.15
    south_hours = len(south) / 60
    persistence = 1 - math.exp(-south_hours / 5)
    compression = q(max((row.pressure or 0) for row in prefix), 2, 25)
    stages = min(1.0, front_count / 3)
    lambda_arrival = (
        0.5
        * (
            max(1e-9, stages * compactness * compression * persistence)
            ** 0.25
        )
        + 0.5 * math.sqrt(max(0, compactness * persistence))
    )

    symh = [row.symh for row in prefix if row.symh is not None]
    ae = [row.ae for row in prefix if row.ae is not None]
    al = [row.al for row in prefix if row.al is not None]
    density = [row.density for row in prefix if row.density is not None]
    bz = [row.bz for row in prefix if row.bz is not None]
    quiet = sum(abs(value) < 20 for value in symh) / len(symh) if symh else 0.0
    plasma = q(statistics.median(density), 2, 15) if density else 0.0
    memory = q(-statistics.median(symh), 0, 80) if symh else 0.0
    conductance = q(
        statistics.quantiles(ae, n=4)[2]
        if len(ae) >= 4
        else (max(ae) if ae else 0),
        100,
        1200,
    )
    tail = 0.5 * q(sum(max(0, -value) for value in bz) / 60, 0, 120)
    tail += 0.5 * q(
        abs(statistics.quantiles(al, n=4)[0]) if len(al) >= 4 else 0,
        100,
        1200,
    )
    pi_e = 1 - (1 - 0.25 * math.sqrt(quiet * plasma)) * (
        1 - 0.35 * math.sqrt(memory * conductance)
    ) * (1 - 0.60 * tail)
    return {
        "feature_rows": len(prefix),
        "valid_feature_rows": len(valid),
        "fronts": front_count,
        "south_hours": round(south_hours, 3),
        "I_Q": iq,
        "V_Bs": vb,
        "Lambda": lambda_arrival,
        "Pi": pi_e,
        "EAGC": iq * (0.5 + lambda_arrival) * (0.5 + pi_e),
    }


def target_after_cutoff(rows: list[Row], cutoff: datetime) -> float | None:
    values = [row.symh for row in rows if row.t >= cutoff and row.symh is not None]
    return min(values, default=None)


def quality_result(
    rows: list[Row],
    *,
    required_fields: list[str],
    gap_fields: list[str],
    minimum_coverage: float,
    maximum_gap: int,
    monotonic: bool,
    duplicates: int,
    prefix_invariant: bool,
) -> tuple[str, dict[str, float], dict[str, int], list[str]]:
    coverages = {key: coverage(rows, key) for key in required_fields}
    gaps = {key: max_gap(rows, key) for key in gap_fields}
    failures: list[str] = []
    if not monotonic or duplicates:
        failures.append("FAIL-TIME")
    if not prefix_invariant:
        failures.append("FAIL-LEAK")
    if any(value < minimum_coverage for value in coverages.values()):
        failures.append("HOLD-DATA")
    if any(value > maximum_gap for value in gaps.values()):
        failures.append("HOLD-GAP")
    for status in ("FAIL-TIME", "FAIL-LEAK", "HOLD-DATA", "HOLD-GAP"):
        if status in failures:
            return status, coverages, gaps, failures
    return "SCORABLE", coverages, gaps, failures


def fit_loocv(items: list[dict[str, Any]], key: str) -> list[float]:
    predictions: list[float] = []
    for index, item in enumerate(items):
        train = [
            candidate
            for candidate_index, candidate in enumerate(items)
            if candidate_index != index
            and candidate.get(key) is not None
            and candidate.get("SYM_H_min") is not None
        ]
        xs = [math.log1p(float(candidate[key])) for candidate in train]
        ys = [-float(candidate["SYM_H_min"]) for candidate in train]
        if len(xs) < 2 or statistics.pvariance(xs) == 0:
            prediction = statistics.mean(ys) if ys else 0
        else:
            mean_x = statistics.mean(xs)
            mean_y = statistics.mean(ys)
            slope = sum(
                (x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)
            ) / sum((x - mean_x) ** 2 for x in xs)
            intercept = mean_y - slope * mean_x
            prediction = intercept + slope * math.log1p(float(item[key]))
        predictions.append(-max(0, prediction))
    return predictions


def rmse(actual: list[float], predicted: list[float]) -> float:
    return math.sqrt(
        sum((observed - estimate) ** 2 for observed, estimate in zip(actual, predicted))
        / len(actual)
    )


def decision_for(
    summaries: list[dict[str, Any]], policy: dict[str, Any]
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    non_scorable = [
        item["event_id"]
        for item in summaries
        if item["quality_status"] != "SCORABLE"
        or item.get("SYM_H_min") is None
    ]
    if non_scorable:
        blockers.append("non-scorable registered events: " + ", ".join(non_scorable))
        return "HOLD-DATA", blockers
    minimum = int(policy["minimum_independent_events"])
    if len(summaries) < minimum:
        blockers.append(f"sample {len(summaries)} is below preregistered minimum {minimum}")
    missing_baselines = sorted(set(policy["required_baselines"]) - IMPLEMENTED_BASELINES)
    if missing_baselines:
        blockers.append("required control baselines not implemented: " + ", ".join(missing_baselines))
    if blockers:
        return "HOLD-SAMPLE", blockers
    return "HOLD-SAMPLE", ["PASS evaluation is not implemented without every acceptance gate"]


def write_event_csv(path: Path, rows: list[Row]) -> None:
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(
            [
                "Time_UTC",
                "Bmag_nT",
                "BZ_GSM_nT",
                "flow_speed_km_s",
                "proton_density_cm3",
                "Pressure_nPa",
                "AE_INDEX_nT",
                "AL_INDEX_nT",
                "SYM_H_nT",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    iso(row.t),
                    row.bmag,
                    row.bz,
                    row.speed,
                    row.density,
                    row.pressure,
                    row.ae,
                    row.al,
                    row.symh,
                ]
            )


def write_registry_csv(
    path: Path,
    rows: list[Row],
    *,
    source_by_month: dict[str, tuple[str, str]],
    cutoff: datetime,
) -> None:
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(
            [
                "Time_UTC",
                "BZ_GSM_nT",
                "flow_speed_km_s",
                "proton_density_cm3",
                "Pressure_nPa",
                "AE_INDEX_nT",
                "AL_INDEX_nT",
                "SYM_H_nT",
                "source",
                "cutoff_rule",
            ]
        )
        for row in rows:
            source_url, source_hash = source_by_month[row.t.strftime("%Y%m")]
            provenance = f"{source_url}#sha256={source_hash}"
            writer.writerow(
                [
                    iso(row.t),
                    row.bz,
                    row.speed,
                    row.density,
                    row.pressure,
                    row.ae,
                    row.al,
                    row.symh,
                    provenance,
                    "FEATURE_PREFIX" if row.t < cutoff else "TARGET_ONLY",
                ]
            )


def main() -> None:
    policy = load_policy()
    events = load_events(policy)
    OUT.mkdir(parents=True, exist_ok=True)
    transfer_dir = OUT / "registry_transfer"
    transfer_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    source_manifest: dict[str, Any] = {}

    for event in events:
        parsed: list[Row] = []
        monotonic = True
        duplicates = 0
        malformed = 0
        source_by_month: dict[str, tuple[str, str]] = {}
        for month in event.months:
            source_path, source_url = acquire(month, policy["source_base"], OUT)
            source_hash = sha256(source_path)
            month_rows, month_monotonic, _month_duplicates, month_malformed = parse(
                source_path, event.start, event.end
            )
            parsed.extend(month_rows)
            monotonic = monotonic and month_monotonic
            malformed += month_malformed
            source_by_month[month] = (source_url, source_hash)
            source_manifest[month] = {
                "file": source_path.name,
                "url": source_url,
                "sha256": source_hash,
                "size_bytes": source_path.stat().st_size,
            }
        if any(after.t <= before.t for before, after in zip(parsed, parsed[1:])):
            monotonic = False
        duplicates = len(parsed) - len({row.t for row in parsed})
        rows = minute_grid(parsed, event.start, event.end)
        features_all = feature_vector(rows, event.cutoff)
        prefix_only = [row for row in rows if row.t < event.cutoff]
        features_prefix = feature_vector(prefix_only, event.cutoff)
        prefix_invariant = features_all == features_prefix
        target = target_after_cutoff(rows, event.cutoff)
        status, coverages, gaps, failures = quality_result(
            rows,
            required_fields=policy["required_coverage_fields"],
            gap_fields=policy["gap_fields"],
            minimum_coverage=float(policy["minimum_coverage"]),
            maximum_gap=int(policy["maximum_gap_minutes"]),
            monotonic=monotonic,
            duplicates=duplicates,
            prefix_invariant=prefix_invariant,
        )
        summary: dict[str, Any] = {
            "event_id": event.event_id,
            "sheet_tab": event.sheet_tab,
            "months": list(event.months),
            "window_start": iso(event.start),
            "forecast_cutoff": iso(event.cutoff),
            "window_end_exclusive": iso(event.end),
            "expected_rows": len(rows),
            "observed_rows": len(parsed),
            "time_monotonic": monotonic,
            "duplicate_timestamps": duplicates,
            "malformed_source_rows": malformed,
            "coverage": coverages,
            "max_gap_min": gaps,
            "prefix_invariant": prefix_invariant,
            "quality_failures": failures,
            "quality_status": status,
            "diagnostic_only": status != "SCORABLE",
            "SYM_H_min": target,
        }
        if features_all:
            summary.update(features_all)
        summaries.append(summary)
        write_event_csv(OUT / f"{event.event_id}.csv", rows)
        write_registry_csv(
            transfer_dir / f"{event.sheet_tab}.csv",
            rows,
            source_by_month=source_by_month,
            cutoff=event.cutoff,
        )

    scorable = [
        item
        for item in summaries
        if item["quality_status"] == "SCORABLE"
        and item.get("SYM_H_min") is not None
    ]
    decision, blockers = decision_for(summaries, policy)
    metrics: dict[str, Any] = {
        "n_registered": len(events),
        "n_scorable": len(scorable),
        "quality_counts": dict(Counter(item["quality_status"] for item in summaries)),
        "minimum_required": int(policy["minimum_independent_events"]),
        "decision": decision,
        "pass_eligible": False,
        "blockers": blockers,
    }
    if len(scorable) >= 4:
        actual = [float(item["SYM_H_min"]) for item in scorable]
        for key in ("I_Q", "V_Bs", "EAGC"):
            predicted = fit_loocv(scorable, key)
            metrics[f"rmse_{key}"] = rmse(actual, predicted)

    (OUT / "event_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "gate_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (OUT / "event_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as target:
        fieldnames = [
            "event_id",
            "quality_status",
            "expected_rows",
            "observed_rows",
            "forecast_cutoff",
            "prefix_invariant",
            "fronts",
            "south_hours",
            "I_Q",
            "V_Bs",
            "Lambda",
            "Pi",
            "EAGC",
            "SYM_H_min",
        ]
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        for item in summaries:
            writer.writerow({key: item.get(key) for key in fieldnames})

    provenance = {
        "protocol_id": policy["protocol_id"],
        "protocol_version": policy["protocol_version"],
        "sensor_version": policy["sensor_version"],
        "dataset_id": policy["dataset_id"],
        "policy_file": str(POLICY_PATH.relative_to(ROOT.parent.parent)),
        "policy_sha256": sha256(POLICY_PATH),
        "runner_sha256": sha256(Path(__file__)),
        "source_files": source_manifest,
        "github_repository": os.environ.get("GITHUB_REPOSITORY"),
        "source_sha": os.environ.get("EAGC_SOURCE_SHA") or os.environ.get("GITHUB_SHA"),
        "workflow_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "implemented_baselines": sorted(IMPLEMENTED_BASELINES),
        "required_baselines": policy["required_baselines"],
        "known_policy_deviations": [
            "Bmag is used by the existing front detector but is not listed in the frozen Sheet parameter row",
            "Newell and Burton/OBrien-McPherron control baselines are not implemented",
            "bootstrap and single-event-dependence acceptance gates are not evaluated",
        ],
    }
    (OUT / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    shutil.copyfile(POLICY_PATH, OUT / "policy.json")

    if len(events) < int(policy["minimum_independent_events"]):
        assert metrics["decision"] != "PASS"
    if any(item["quality_status"] != "SCORABLE" for item in summaries):
        assert metrics["decision"] == "HOLD-DATA"
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
