from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
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
    "by": 17,
    "bz": 18,
    "speed": 21,
    "density": 25,
    "pressure": 27,
    "ae": 37,
    "al": 38,
    "symh": 41,
}
FILLS = {
    "bmag": 9999.99,
    "by": 9999.99,
    "bz": 9999.99,
    "speed": 99999.9,
    "density": 999.99,
    "pressure": 99.99,
    "ae": 99999.0,
    "al": 99999.0,
    "symh": 99999.0,
}
IMPLEMENTED_BASELINES = {
    "V_Bs",
    "I_Q",
    "Newell",
    "Burton_OBrien_McPherron",
}
SCORING_FIELDS = (*sorted(IMPLEMENTED_BASELINES), "EAGC")
COHORTS = ("development", "validation")


@dataclass(frozen=True)
class Event:
    event_id: str
    sheet_tab: str
    months: tuple[str, ...]
    start: datetime
    cutoff: datetime
    end: datetime
    cohort: str


@dataclass(frozen=True)
class Row:
    t: datetime
    bmag: float | None
    by: float | None
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
        "forecast_cutoff_rule",
        "required_coverage_fields",
        "gap_fields",
        "minimum_coverage",
        "minimum_target_coverage",
        "maximum_gap_minutes",
        "minimum_independent_events",
        "minimum_development_events",
        "minimum_rmse_improvement",
        "minimum_bootstrap_probability",
        "bootstrap_replicates",
        "bootstrap_seed",
        "required_baselines",
        "event_catalog",
        "model_references",
        "eagc_model",
        "development_events",
        "validation_events",
    }
    missing = sorted(required - policy.keys())
    if missing:
        raise ValueError(f"policy missing required keys: {missing}")
    minimum_coverage = policy["minimum_coverage"]
    if (
        isinstance(minimum_coverage, bool)
        or not isinstance(minimum_coverage, (int, float))
        or not 0 < minimum_coverage <= 1
    ):
        raise ValueError("minimum_coverage must be in (0, 1]")
    minimum_target_coverage = policy["minimum_target_coverage"]
    if (
        isinstance(minimum_target_coverage, bool)
        or not isinstance(minimum_target_coverage, (int, float))
        or not 0 < minimum_target_coverage <= 1
    ):
        raise ValueError("minimum_target_coverage must be in (0, 1]")
    maximum_gap = policy["maximum_gap_minutes"]
    if (
        isinstance(maximum_gap, bool)
        or not isinstance(maximum_gap, int)
        or maximum_gap < 0
    ):
        raise ValueError("maximum_gap_minutes must be a non-negative integer")
    minimum_events = policy["minimum_independent_events"]
    if (
        isinstance(minimum_events, bool)
        or not isinstance(minimum_events, int)
        or minimum_events <= 0
    ):
        raise ValueError("minimum_independent_events must be a positive integer")
    minimum_improvement = policy["minimum_rmse_improvement"]
    if (
        isinstance(minimum_improvement, bool)
        or not isinstance(minimum_improvement, (int, float))
        or not 0 < minimum_improvement < 1
    ):
        raise ValueError("minimum_rmse_improvement must be in (0, 1)")
    bootstrap_probability = policy["minimum_bootstrap_probability"]
    if (
        isinstance(bootstrap_probability, bool)
        or not isinstance(bootstrap_probability, (int, float))
        or not 0 < bootstrap_probability <= 1
    ):
        raise ValueError("minimum_bootstrap_probability must be in (0, 1]")
    bootstrap_replicates = policy["bootstrap_replicates"]
    if (
        isinstance(bootstrap_replicates, bool)
        or not isinstance(bootstrap_replicates, int)
        or bootstrap_replicates < 1000
    ):
        raise ValueError("bootstrap_replicates must be an integer of at least 1000")
    bootstrap_seed = policy["bootstrap_seed"]
    if isinstance(bootstrap_seed, bool) or not isinstance(bootstrap_seed, int):
        raise ValueError("bootstrap_seed must be an integer")
    event_catalog = policy["event_catalog"]
    if (
        not isinstance(event_catalog, dict)
        or not isinstance(event_catalog.get("url"), str)
        or not event_catalog["url"].startswith("https://")
        or not isinstance(event_catalog.get("selection_rule"), str)
        or not event_catalog["selection_rule"]
    ):
        raise ValueError("invalid event_catalog")
    model_references = policy["model_references"]
    if (
        not isinstance(model_references, dict)
        or any(
            not isinstance(model_references.get(name), str)
            or not model_references[name].startswith("https://")
            for name in ("Newell", "Burton_OBrien_McPherron")
        )
    ):
        raise ValueError("invalid model_references")

    valid_fields = {field.name for field in fields(Row)} - {"t"}
    required_fields = policy["required_coverage_fields"]
    gap_fields = policy["gap_fields"]
    for label, configured_fields in (
        ("required_coverage_fields", required_fields),
        ("gap_fields", gap_fields),
    ):
        if (
            not isinstance(configured_fields, list)
            or not configured_fields
            or any(
                not isinstance(key, str) or key not in valid_fields
                for key in configured_fields
            )
            or len(configured_fields) != len(set(configured_fields))
        ):
            raise ValueError(f"invalid {label}")
    if not set(gap_fields).issubset(required_fields):
        raise ValueError("gap_fields must be a subset of required_coverage_fields")
    for cohort in COHORTS:
        configured = policy[f"{cohort}_events"]
        if not isinstance(configured, list) or not configured:
            raise ValueError(f"policy must register at least one {cohort} event")
    minimum_development = policy["minimum_development_events"]
    if (
        isinstance(minimum_development, bool)
        or not isinstance(minimum_development, int)
        or minimum_development <= 0
    ):
        raise ValueError("minimum_development_events must be a positive integer")
    if (
        not isinstance(policy["required_baselines"], list)
        or not policy["required_baselines"]
        or any(
            not isinstance(name, str) or not name
            for name in policy["required_baselines"]
        )
        or len(policy["required_baselines"]) != len(set(policy["required_baselines"]))
    ):
        raise ValueError("invalid required_baselines")
    model = policy["eagc_model"]
    if (
        not isinstance(model, dict)
        or model.get("kind") != "standardized_ridge"
        or not isinstance(model.get("features"), list)
        or not model["features"]
        or len(model["features"]) != len(set(model["features"]))
        or any(
            not isinstance(name, str) or not name
            for name in model["features"]
        )
        or isinstance(model.get("alpha"), bool)
        or not isinstance(model.get("alpha"), (int, float))
        or model["alpha"] <= 0
    ):
        raise ValueError("invalid eagc_model")
    return policy


def load_events(policy: dict[str, Any]) -> list[Event]:
    try:
        prefix_minutes = int(policy["forecast_cutoff_rule"]["prefix_minutes"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid forecast cutoff rule") from error
    if prefix_minutes <= 0:
        raise ValueError("forecast cutoff prefix must be positive")

    events = []
    for cohort in COHORTS:
        events.extend(
            Event(
                event_id=item["event_id"],
                sheet_tab=item["sheet_tab"],
                months=tuple(item["months"]),
                start=dt(item["start"]),
                cutoff=dt(item["cutoff"]),
                end=dt(item["end"]),
                cohort=cohort,
            )
            for item in policy[f"{cohort}_events"]
        )
    for event in events:
        for label, value in (
            ("event_id", event.event_id),
            ("sheet_tab", event.sheet_tab),
        ):
            if (
                not value
                or value in {".", ".."}
                or Path(value).name != value
                or "\\" in value
            ):
                raise ValueError(f"invalid {label}: {value!r}")
    event_ids = [event.event_id for event in events]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("event_id values must be unique")
    sheet_tabs = [event.sheet_tab for event in events]
    if len(sheet_tabs) != len(set(sheet_tabs)):
        raise ValueError("sheet_tab values must be unique")

    for event in events:
        for label, value in (
            ("start", event.start),
            ("cutoff", event.cutoff),
            ("end", event.end),
        ):
            if value.utcoffset() != timedelta(0):
                raise ValueError(f"{event.event_id} {label} must use UTC")
            if value.second or value.microsecond:
                raise ValueError(
                    f"{event.event_id} {label} must align to a whole minute"
                )
        if not event.start < event.cutoff < event.end:
            raise ValueError(f"invalid cutoff ordering for {event.event_id}")
        expected_cutoff = event.start + timedelta(minutes=prefix_minutes)
        if event.cutoff != expected_cutoff:
            raise ValueError(
                f"{event.event_id} cutoff does not match the forecast cutoff rule"
            )
        required_months: set[str] = set()
        cursor = event.start
        last_included = event.end - timedelta(minutes=1)
        while (cursor.year, cursor.month) <= (
            last_included.year,
            last_included.month,
        ):
            required_months.add(cursor.strftime("%Y%m"))
            if cursor.month == 12:
                cursor = cursor.replace(
                    year=cursor.year + 1,
                    month=1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            else:
                cursor = cursor.replace(
                    month=cursor.month + 1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
        if not required_months.issubset(event.months):
            raise ValueError(
                f"{event.event_id} does not list every month crossed by its window"
            )
        if len(event.months) != len(required_months) or set(event.months) != required_months:
            raise ValueError(
                f"{event.event_id} lists months outside its registered window"
            )
        if event.months != tuple(sorted(required_months)):
            raise ValueError(
                f"{event.event_id} months must be listed in chronological order"
            )

    ordered_events = sorted(events, key=lambda event: event.start)
    for previous, current in zip(ordered_events, ordered_events[1:]):
        if current.start < previous.end:
            raise ValueError(
                f"registered event windows overlap: "
                f"{previous.event_id}, {current.event_id}"
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
                    clean("by", parts[IDX["by"]]),
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


def interpolate_values(
    rows: list[Row], key: str, maximum_gap: int
) -> list[float] | None:
    values = [
        float(value) if (value := getattr(row, key)) is not None else None
        for row in rows
    ]
    if not values or all(value is None for value in values):
        return None
    index = 0
    while index < len(values):
        if values[index] is not None:
            index += 1
            continue
        start = index
        while index < len(values) and values[index] is None:
            index += 1
        stop = index
        if stop - start > maximum_gap:
            return None
        left = values[start - 1] if start else None
        right = values[stop] if stop < len(values) else None
        if left is None and right is None:
            return None
        if left is None:
            values[start:stop] = [right] * (stop - start)
        elif right is None:
            values[start:stop] = [left] * (stop - start)
        else:
            width = stop - start + 1
            values[start:stop] = [
                left + (right - left) * offset / width
                for offset in range(1, stop - start + 1)
            ]
    return [float(value) for value in values]


def newell_coupling(rows: list[Row]) -> float | None:
    """Mean Newell et al. (2007) dPhi/dt coupling over the prefix."""
    values: list[float] = []
    for row in rows:
        if row.by is None or row.bz is None or row.speed is None:
            continue
        transverse = math.hypot(row.by, row.bz)
        if transverse <= 0 or row.speed <= 0:
            values.append(0.0)
            continue
        clock_angle = math.atan2(abs(row.by), row.bz)
        values.append(
            row.speed ** (4 / 3)
            * transverse ** (2 / 3)
            * math.sin(clock_angle / 2) ** (8 / 3)
        )
    return statistics.fmean(values) if values else None


def burton_obrien_mcpherron(
    rows: list[Row], maximum_gap: int = 15
) -> float | None:
    """Return the OM model's peak disturbance magnitude in the prefix.

    The pressure-corrected SYM-H state is integrated at one-minute cadence
    using O'Brien and McPherron (2000), with short quality-permitted gaps
    linearly interpolated before integration.
    """
    speed = interpolate_values(rows, "speed", maximum_gap)
    bz = interpolate_values(rows, "bz", maximum_gap)
    pressure = interpolate_values(rows, "pressure", maximum_gap)
    symh = interpolate_values(rows, "symh", maximum_gap)
    if any(series is None for series in (speed, bz, pressure, symh)):
        return None
    assert speed is not None
    assert bz is not None
    assert pressure is not None
    assert symh is not None

    dst_star = symh[0] - 7.26 * math.sqrt(max(pressure[0], 0.0)) + 11.0
    minimum_prediction = symh[0]
    for index in range(1, len(rows)):
        electric_field = speed[index] * max(0.0, -bz[index]) * 1e-3
        injection = (
            -4.4 * (electric_field - 0.49)
            if electric_field > 0.49
            else 0.0
        )
        decay_hours = 2.4 * math.exp(9.74 / (4.69 + electric_field))
        dst_star += (injection - dst_star / decay_hours) / 60
        prediction = (
            dst_star
            + 7.26 * math.sqrt(max(pressure[index], 0.0))
            - 11.0
        )
        minimum_prediction = min(minimum_prediction, prediction)
    return max(0.0, -minimum_prediction)


def feature_vector(
    rows: list[Row], cutoff: datetime, maximum_gap: int = 15
) -> dict[str, float | int] | None:
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
    recent_symh = [
        row.symh for row in prefix[-60:] if row.symh is not None
    ]
    recent_pressure = [
        row.pressure for row in prefix[-180:] if row.pressure is not None
    ]
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
    newell = newell_coupling(prefix)
    return {
        "feature_rows": len(prefix),
        "valid_feature_rows": len(valid),
        "fronts": front_count,
        "south_hours": round(south_hours, 3),
        "SYM_H_prefix_min": -min(symh) if symh else None,
        "SYM_H_recent": (
            -statistics.median(recent_symh) if recent_symh else None
        ),
        "pressure_peak": max(
            row.pressure for row in prefix if row.pressure is not None
        ),
        "pressure_recent": statistics.median(recent_pressure),
        "I_Q": iq,
        "V_Bs": vb,
        "Newell": newell,
        "log_Newell": math.log1p(newell) if newell is not None else None,
        "Burton_OBrien_McPherron": burton_obrien_mcpherron(
            prefix, maximum_gap
        ),
        "Lambda": lambda_arrival,
        "Pi": pi_e,
        "EAGC": iq * (0.5 + lambda_arrival) * (0.5 + pi_e),
    }


def target_after_cutoff(rows: list[Row], cutoff: datetime) -> float | None:
    values = [row.symh for row in rows if row.t >= cutoff and row.symh is not None]
    return min(values, default=None)


def quality_result(
    feature_rows: list[Row],
    *,
    target_rows: list[Row] | None = None,
    target_fields: tuple[str, ...] = ("symh",),
    required_fields: list[str],
    gap_fields: list[str],
    minimum_coverage: float,
    maximum_gap: int,
    target_minimum_coverage: float | None = None,
    monotonic: bool,
    duplicates: int,
    prefix_invariant: bool,
    prefix_features_available: bool = True,
) -> tuple[
    str,
    dict[str, float],
    dict[str, int],
    dict[str, float],
    dict[str, int],
    list[str],
]:
    coverages = {key: coverage(feature_rows, key) for key in required_fields}
    gaps = {key: max_gap(feature_rows, key) for key in gap_fields}
    target_coverages = (
        {key: coverage(target_rows, key) for key in target_fields}
        if target_rows is not None
        else {}
    )
    target_gaps = (
        {key: max_gap(target_rows, key) for key in target_fields}
        if target_rows is not None
        else {}
    )
    failures: list[str] = []
    if not monotonic or duplicates:
        failures.append("FAIL-TIME")
    if not prefix_invariant:
        failures.append("FAIL-LEAK")
    if not prefix_features_available:
        failures.append("HOLD-DATA")
    target_threshold = (
        minimum_coverage
        if target_minimum_coverage is None
        else target_minimum_coverage
    )
    if (
        (
            any(value < minimum_coverage for value in coverages.values())
            or any(
                value < target_threshold
                for value in target_coverages.values()
            )
        )
        and "HOLD-DATA" not in failures
    ):
        failures.append("HOLD-DATA")
    if any(value > maximum_gap for value in (*gaps.values(), *target_gaps.values())):
        failures.append("HOLD-GAP")
    for status in ("FAIL-TIME", "FAIL-LEAK", "HOLD-DATA", "HOLD-GAP"):
        if status in failures:
            return (
                status,
                coverages,
                gaps,
                target_coverages,
                target_gaps,
                failures,
            )
    return (
        "SCORABLE",
        coverages,
        gaps,
        target_coverages,
        target_gaps,
        failures,
    )


def solve_linear_system(
    matrix: list[list[float]], vector: list[float]
) -> list[float]:
    augmented = [[*row, value] for row, value in zip(matrix, vector)]
    for column in range(len(vector)):
        pivot = max(
            range(column, len(vector)),
            key=lambda row: abs(augmented[row][column]),
        )
        augmented[column], augmented[pivot] = (
            augmented[pivot],
            augmented[column],
        )
        divisor = augmented[column][column]
        if abs(divisor) < 1e-12:
            raise ValueError("singular regression system")
        augmented[column] = [
            value / divisor for value in augmented[column]
        ]
        for row in range(len(vector)):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(
                    augmented[row], augmented[column]
                )
            ]
    return [row[-1] for row in augmented]


def fit_univariate(
    items: list[dict[str, Any]], key: str
) -> dict[str, Any]:
    xs = [math.log1p(float(item[key])) for item in items]
    ys = [-float(item["SYM_H_min"]) for item in items]
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    slope = (
        sum(
            (x - mean_x) * (y - mean_y)
            for x, y in zip(xs, ys)
        )
        / denominator
        if denominator
        else 0.0
    )
    return {
        "kind": "log_linear",
        "feature": key,
        "intercept": mean_y - slope * mean_x,
        "slope": slope,
    }


def predict_univariate(
    model: dict[str, Any], item: dict[str, Any]
) -> float:
    magnitude = float(model["intercept"]) + float(model["slope"]) * math.log1p(
        float(item[model["feature"]])
    )
    return -max(0.0, magnitude)


def fit_ridge(
    items: list[dict[str, Any]],
    feature_names: list[str],
    alpha: float,
) -> dict[str, Any]:
    predictors = [
        [float(item[name]) for name in feature_names] for item in items
    ]
    targets = [-float(item["SYM_H_min"]) for item in items]
    means = [
        statistics.fmean(row[column] for row in predictors)
        for column in range(len(feature_names))
    ]
    scales = [
        statistics.pstdev(row[column] for row in predictors) or 1.0
        for column in range(len(feature_names))
    ]
    standardized = [
        [
            (value - means[column]) / scales[column]
            for column, value in enumerate(row)
        ]
        for row in predictors
    ]
    intercept = statistics.fmean(targets)
    centered_targets = [value - intercept for value in targets]
    system = [
        [
            sum(row[left] * row[right] for row in standardized)
            + (alpha if left == right else 0.0)
            for right in range(len(feature_names))
        ]
        for left in range(len(feature_names))
    ]
    target = [
        sum(
            row[column] * value
            for row, value in zip(standardized, centered_targets)
        )
        for column in range(len(feature_names))
    ]
    coefficients = solve_linear_system(system, target)
    return {
        "kind": "standardized_ridge",
        "features": feature_names,
        "alpha": alpha,
        "intercept": intercept,
        "coefficients": coefficients,
        "means": means,
        "scales": scales,
    }


def predict_ridge(model: dict[str, Any], item: dict[str, Any]) -> float:
    magnitude = float(model["intercept"])
    for name, coefficient, mean, scale in zip(
        model["features"],
        model["coefficients"],
        model["means"],
        model["scales"],
    ):
        magnitude += (
            float(coefficient)
            * (float(item[name]) - float(mean))
            / float(scale)
        )
    return -max(0.0, magnitude)


def fit_models(
    development: list[dict[str, Any]], policy: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    models = {
        baseline: fit_univariate(development, baseline)
        for baseline in policy["required_baselines"]
    }
    configured = policy["eagc_model"]
    models["EAGC"] = fit_ridge(
        development,
        list(configured["features"]),
        float(configured["alpha"]),
    )
    return models


def predict_models(
    models: dict[str, dict[str, Any]],
    items: list[dict[str, Any]],
) -> dict[str, list[float]]:
    return {
        name: [
            (
                predict_ridge(model, item)
                if name == "EAGC"
                else predict_univariate(model, item)
            )
            for item in items
        ]
        for name, model in models.items()
    }


def cross_validated_predictions(
    development: list[dict[str, Any]], policy: dict[str, Any]
) -> dict[str, list[float]]:
    predictions = {
        name: [] for name in (*policy["required_baselines"], "EAGC")
    }
    for omitted, item in enumerate(development):
        train = [
            candidate
            for index, candidate in enumerate(development)
            if index != omitted
        ]
        fold_predictions = predict_models(fit_models(train, policy), [item])
        for name in predictions:
            predictions[name].append(fold_predictions[name][0])
    return predictions


def fit_loocv(items: list[dict[str, Any]], key: str) -> list[float]:
    """Backward-compatible univariate leave-one-event-out predictions."""
    predictions: list[float] = []
    for omitted, item in enumerate(items):
        train = [
            candidate
            for index, candidate in enumerate(items)
            if index != omitted
        ]
        predictions.append(
            predict_univariate(fit_univariate(train, key), item)
        )
    return predictions


def rmse(actual: list[float], predicted: list[float]) -> float:
    return math.sqrt(
        sum((observed - estimate) ** 2 for observed, estimate in zip(actual, predicted))
        / len(actual)
    )


def relative_improvement(candidate_rmse: float, baseline_rmse: float) -> float:
    if baseline_rmse == 0:
        return 0.0 if candidate_rmse == 0 else -1.0
    return (baseline_rmse - candidate_rmse) / baseline_rmse


def paired_bootstrap_probability(
    actual: list[float],
    candidate: list[float],
    baseline: list[float],
    *,
    replicates: int,
    seed: int,
) -> float:
    """Probability that candidate MSE is lower under paired resampling."""
    differences = [
        (observed - control) ** 2 - (observed - estimate) ** 2
        for observed, estimate, control in zip(actual, candidate, baseline)
    ]
    rng = random.Random(seed)
    wins = 0
    for _ in range(replicates):
        mean_difference = statistics.fmean(
            differences[rng.randrange(len(differences))]
            for _ in range(len(differences))
        )
        if mean_difference > 0:
            wins += 1
    return wins / replicates


def single_event_improvements(
    event_ids: list[str],
    actual: list[float],
    candidate: list[float],
    baseline: list[float],
) -> dict[str, float]:
    improvements: dict[str, float] = {}
    for omitted in range(len(actual)):
        retained = [index for index in range(len(actual)) if index != omitted]
        candidate_rmse = rmse(
            [actual[index] for index in retained],
            [candidate[index] for index in retained],
        )
        baseline_rmse = rmse(
            [actual[index] for index in retained],
            [baseline[index] for index in retained],
        )
        improvements[event_ids[omitted]] = relative_improvement(
            candidate_rmse, baseline_rmse
        )
    return improvements


def evaluate_gate(
    summaries: list[dict[str, Any]], policy: dict[str, Any]
) -> tuple[str, list[str], dict[str, Any]]:
    blockers: list[str] = []
    development = [
        item for item in summaries if item.get("cohort") == "development"
    ]
    validation = [
        item for item in summaries if item.get("cohort") == "validation"
    ]
    required_features = {
        *policy["required_baselines"],
        *policy["eagc_model"]["features"],
    }
    non_scorable = [
        item["event_id"]
        for item in summaries
        if item["quality_status"] != "SCORABLE"
        or item.get("SYM_H_min") is None
        or any(item.get(key) is None for key in required_features)
    ]
    if non_scorable:
        blockers.append("non-scorable registered events: " + ", ".join(non_scorable))
    minimum_development = int(policy["minimum_development_events"])
    minimum_validation = int(policy["minimum_independent_events"])
    if len(development) < minimum_development:
        blockers.append(
            f"development sample {len(development)} is below preregistered "
            f"minimum {minimum_development}"
        )
    if len(validation) < minimum_validation:
        blockers.append(
            f"validation sample {len(validation)} is below preregistered "
            f"minimum {minimum_validation}"
        )
    missing_baselines = sorted(set(policy["required_baselines"]) - IMPLEMENTED_BASELINES)
    if missing_baselines:
        blockers.append(
            "required control baselines not implemented: "
            + ", ".join(missing_baselines)
        )
    if non_scorable:
        return "HOLD-DATA", blockers, {}
    if (
        len(development) < minimum_development
        or len(validation) < minimum_validation
        or missing_baselines
    ):
        return "HOLD-SAMPLE", blockers, {}

    models = fit_models(development, policy)
    predictions = predict_models(models, validation)
    actual = [float(item["SYM_H_min"]) for item in validation]
    event_ids = [str(item["event_id"]) for item in validation]
    rmses = {key: rmse(actual, prediction) for key, prediction in predictions.items()}
    development_actual = [
        float(item["SYM_H_min"]) for item in development
    ]
    development_predictions = cross_validated_predictions(
        development, policy
    )
    development_rmse = {
        name: rmse(development_actual, prediction)
        for name, prediction in development_predictions.items()
    }
    minimum_improvement = float(policy["minimum_rmse_improvement"])
    minimum_probability = float(policy["minimum_bootstrap_probability"])
    comparisons: dict[str, Any] = {}
    acceptance_failed = False
    for baseline in policy["required_baselines"]:
        improvement = relative_improvement(rmses["EAGC"], rmses[baseline])
        probability = paired_bootstrap_probability(
            actual,
            predictions["EAGC"],
            predictions[baseline],
            replicates=int(policy["bootstrap_replicates"]),
            seed=int(policy["bootstrap_seed"]),
        )
        omitted_improvements = single_event_improvements(
            event_ids,
            actual,
            predictions["EAGC"],
            predictions[baseline],
        )
        worst_event, worst_improvement = min(
            omitted_improvements.items(), key=lambda item: item[1]
        )
        improvement_pass = improvement >= minimum_improvement
        bootstrap_pass = probability >= minimum_probability
        single_event_pass = worst_improvement >= minimum_improvement
        comparisons[baseline] = {
            "rmse_improvement": improvement,
            "bootstrap_probability": probability,
            "minimum_leave_one_event_out_improvement": worst_improvement,
            "worst_omitted_event": worst_event,
            "rmse_gate_pass": improvement_pass,
            "bootstrap_gate_pass": bootstrap_pass,
            "single_event_gate_pass": single_event_pass,
        }
        if not improvement_pass:
            blockers.append(
                f"EAGC RMSE improvement vs {baseline} is {improvement:.6f}, "
                f"below {minimum_improvement:.6f}"
            )
        if not bootstrap_pass:
            blockers.append(
                f"EAGC bootstrap probability vs {baseline} is {probability:.6f}, "
                f"below {minimum_probability:.6f}"
            )
        if not single_event_pass:
            blockers.append(
                f"EAGC improvement vs {baseline} falls to "
                f"{worst_improvement:.6f} when {worst_event} is omitted"
            )
        acceptance_failed = acceptance_failed or not (
            improvement_pass and bootstrap_pass and single_event_pass
        )
    details = {
        "rmse": rmses,
        "development_leave_one_event_out_rmse": development_rmse,
        "comparisons": comparisons,
        "bootstrap_replicates": int(policy["bootstrap_replicates"]),
        "bootstrap_seed": int(policy["bootstrap_seed"]),
        "fitted_models": models,
        "validation_predictions": [
            {
                "event_id": event_id,
                "observed_SYM_H_min": observed,
                **{
                    f"{name}_prediction": predictions[name][index]
                    for name in predictions
                },
            }
            for index, (event_id, observed) in enumerate(
                zip(event_ids, actual)
            )
        ],
    }
    return ("REJECT" if acceptance_failed else "PASS"), blockers, details


def decision_for(
    summaries: list[dict[str, Any]], policy: dict[str, Any]
) -> tuple[str, list[str]]:
    decision, blockers, _ = evaluate_gate(summaries, policy)
    return decision, blockers


def write_event_csv(path: Path, rows: list[Row]) -> None:
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(
            [
                "Time_UTC",
                "Bmag_nT",
                "BY_GSM_nT",
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
                    row.by,
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
                "BY_GSM_nT",
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
                    row.by,
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
    all_events = load_events(policy)
    requested_cohort = os.environ.get("EAGC_COHORT")
    if requested_cohort and requested_cohort not in COHORTS:
        raise ValueError(
            f"EAGC_COHORT must be one of {', '.join(COHORTS)}"
        )
    events = [
        event
        for event in all_events
        if requested_cohort is None or event.cohort == requested_cohort
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    transfer_dir = OUT / "registry_transfer"
    transfer_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    source_manifest: dict[str, Any] = {}
    registered_by_id = {
        item["event_id"]: item
        for cohort in COHORTS
        for item in policy[f"{cohort}_events"]
    }

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
        features_all = feature_vector(
            rows, event.cutoff, int(policy["maximum_gap_minutes"])
        )
        prefix_only = [row for row in rows if row.t < event.cutoff]
        target_only = [row for row in rows if row.t >= event.cutoff]
        features_prefix = feature_vector(
            prefix_only, event.cutoff, int(policy["maximum_gap_minutes"])
        )
        prefix_invariant = features_all == features_prefix
        target = target_after_cutoff(rows, event.cutoff)
        (
            status,
            coverages,
            gaps,
            target_coverages,
            target_gaps,
            failures,
        ) = quality_result(
            prefix_only,
            target_rows=target_only,
            required_fields=policy["required_coverage_fields"],
            gap_fields=policy["gap_fields"],
            minimum_coverage=float(policy["minimum_coverage"]),
            maximum_gap=int(policy["maximum_gap_minutes"]),
            target_minimum_coverage=float(
                policy["minimum_target_coverage"]
            ),
            monotonic=monotonic,
            duplicates=duplicates,
            prefix_invariant=prefix_invariant,
            prefix_features_available=features_all is not None,
        )
        registered = registered_by_id[event.event_id]
        summary: dict[str, Any] = {
            "event_id": event.event_id,
            "sheet_tab": event.sheet_tab,
            "cohort": event.cohort,
            **{
                key: value
                for key, value in registered.items()
                if key.startswith("catalog_")
            },
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
            "coverage_scope": "FEATURE_PREFIX",
            "max_gap_min": gaps,
            "target_coverage": target_coverages,
            "target_max_gap_min": target_gaps,
            "target_scope": "TARGET_ONLY",
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
        and all(
            item.get(key) is not None
            for key in (
                *policy["required_baselines"],
                *policy["eagc_model"]["features"],
            )
        )
    ]
    cohort_counts = {
        cohort: sum(item["cohort"] == cohort for item in summaries)
        for cohort in COHORTS
    }
    scorable_by_cohort = {
        cohort: sum(
            item["cohort"] == cohort
            and item["quality_status"] == "SCORABLE"
            for item in summaries
        )
        for cohort in COHORTS
    }
    decision, blockers, acceptance = evaluate_gate(summaries, policy)
    metrics: dict[str, Any] = {
        "n_registered": len(events),
        "n_scorable": len(scorable),
        "registered_by_cohort": cohort_counts,
        "scorable_by_cohort": scorable_by_cohort,
        "quality_counts": dict(Counter(item["quality_status"] for item in summaries)),
        "minimum_development_required": int(
            policy["minimum_development_events"]
        ),
        "minimum_validation_required": int(
            policy["minimum_independent_events"]
        ),
        "decision": decision,
        "pass_eligible": decision == "PASS",
        "blockers": blockers,
        **acceptance,
    }
    development_scorable = [
        item for item in scorable if item["cohort"] == "development"
    ]
    if (
        len(development_scorable)
        >= int(policy["minimum_development_events"])
        and "rmse" not in metrics
    ):
        actual = [
            float(item["SYM_H_min"]) for item in development_scorable
        ]
        predictions = cross_validated_predictions(
            development_scorable, policy
        )
        metrics["development_leave_one_event_out_rmse"] = {
            name: rmse(actual, predicted)
            for name, predicted in predictions.items()
        }

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
            "cohort",
            "quality_status",
            "expected_rows",
            "observed_rows",
            "forecast_cutoff",
            "prefix_invariant",
            "fronts",
            "south_hours",
            "SYM_H_prefix_min",
            "SYM_H_recent",
            "pressure_peak",
            "pressure_recent",
            "I_Q",
            "V_Bs",
            "Newell",
            "log_Newell",
            "Burton_OBrien_McPherron",
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
        "event_catalog": policy["event_catalog"],
        "github_repository": os.environ.get("GITHUB_REPOSITORY"),
        "source_sha": os.environ.get("EAGC_SOURCE_SHA") or os.environ.get("GITHUB_SHA"),
        "workflow_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "implemented_baselines": sorted(IMPLEMENTED_BASELINES),
        "required_baselines": policy["required_baselines"],
        "model_references": policy["model_references"],
        "known_policy_deviations": [],
        "processed_cohort": requested_cohort or "all",
    }
    (OUT / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    shutil.copyfile(POLICY_PATH, OUT / "policy.json")

    if any(
        cohort_counts[cohort]
        < int(
            policy[
                "minimum_development_events"
                if cohort == "development"
                else "minimum_independent_events"
            ]
        )
        for cohort in COHORTS
    ):
        assert metrics["decision"] != "PASS"
    if any(item["quality_status"] != "SCORABLE" for item in summaries):
        assert metrics["decision"] == "HOLD-DATA"
    if metrics["decision"] == "PASS":
        assert scorable_by_cohort["development"] >= int(
            policy["minimum_development_events"]
        )
        assert scorable_by_cohort["validation"] >= int(
            policy["minimum_independent_events"]
        )
        assert all(
            comparison["rmse_gate_pass"]
            and comparison["bootstrap_gate_pass"]
            and comparison["single_event_gate_pass"]
            for comparison in metrics["comparisons"].values()
        )
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
