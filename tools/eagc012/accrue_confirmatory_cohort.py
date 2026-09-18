#!/usr/bin/env python3
"""Build a target-blind candidate manifest from a versioned ICMECAT CSV snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ALLOWLIST = ("icmecat_id", "sc_insitu", "icme_start_time", "mo_end_time")
COHORT_SIZE = 20
CUTOFF_MINUTES = 720
MINIMUM_TARGET_MINUTES = 720


def utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone: {value}")
    parsed = parsed.astimezone(timezone.utc)
    if parsed.second or parsed.microsecond:
        raise ValueError(f"timestamp is not a whole minute: {value}")
    return parsed


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def overlaps(left: dict[str, str], right: dict[str, str]) -> bool:
    return utc(left["icme_start_time"]) < utc(right["mo_end_time"]) and utc(right["icme_start_time"]) < utc(left["mo_end_time"])


def build_manifest(
    catalog_path: Path,
    *,
    source_url: str,
    source_version: str,
    retrieved_at: str,
    freeze_commit: str,
    freeze_committed_at: str,
) -> dict[str, Any]:
    retrieved = utc(retrieved_at)
    frozen = utc(freeze_committed_at)
    if retrieved <= frozen:
        raise ValueError("catalog snapshot must be retrieved strictly after the freeze commit")
    if len(freeze_commit) != 40 or any(char not in "0123456789abcdef" for char in freeze_commit.lower()):
        raise ValueError("freeze_commit must be a full hexadecimal SHA")
    match = re.fullmatch(r"(\d+)\.(\d+)", source_version)
    if match is None or tuple(map(int, match.groups())) < (2, 3):
        raise ValueError("source_version must be HELIO4CAST ICMECAT 2.3 or newer")
    expected_prefix = "https://helioforecast.space/static/sync/icmecat/HELIO4CAST_ICMECAT_v"
    if not source_url.startswith(expected_prefix) or not source_url.endswith(".csv"):
        raise ValueError("source_url must be an official versioned HELIO4CAST ICMECAT CSV")

    raw = catalog_path.read_bytes()
    with catalog_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in ALLOWLIST if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"catalog missing allowlisted columns: {', '.join(missing)}")
        projected = [{name: (row[name] or "").strip() for name in ALLOWLIST} for row in reader]

    eligible: list[dict[str, str]] = []
    for row in projected:
        if row["sc_insitu"] != "Wind":
            continue
        start = utc(row["icme_start_time"])
        end = utc(row["mo_end_time"])
        if start <= frozen:
            continue
        if end - (start + timedelta(minutes=CUTOFF_MINUTES)) < timedelta(minutes=MINIMUM_TARGET_MINUTES):
            continue
        eligible.append(row)
    eligible.sort(key=lambda row: (utc(row["icme_start_time"]), row["icmecat_id"]))

    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in eligible:
        identifier = row["icmecat_id"]
        if not identifier:
            raise ValueError("eligible row has an empty icmecat_id")
        if identifier in seen:
            raise ValueError(f"duplicate icmecat_id: {identifier}")
        seen.add(identifier)
        if any(overlaps(row, prior) for prior in selected):
            continue
        selected.append({
            "icmecat_id": identifier,
            "sc_insitu": "Wind",
            "icme_start_time": iso(utc(row["icme_start_time"])),
            "cutoff": iso(utc(row["icme_start_time"]) + timedelta(minutes=CUTOFF_MINUTES)),
            "mo_end_time": iso(utc(row["mo_end_time"])),
        })
        if len(selected) == COHORT_SIZE:
            break

    projection_bytes = json.dumps(projected, sort_keys=True, separators=(",", ":")).encode()
    return {
        "protocol_id": "TZAR-RESEARCH-EAGC-012-CONFIRMATORY-ICME",
        "protocol_version": "1.0.0-prospective",
        "state": "FROZEN-CANDIDATE" if len(selected) == COHORT_SIZE else "OPEN-ACCRUAL",
        "target_access_permitted": False,
        "target_access_guard": "Commit this complete 20-event manifest, then use a later commit to retrieve OMNI targets.",
        "freeze": {
            "commit": freeze_commit,
            "committed_at": iso(frozen),
        },
        "catalog_snapshot": {
            "source_url": source_url,
            "source_version": source_version,
            "retrieved_at": iso(retrieved),
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "projected_rows_sha256": hashlib.sha256(projection_bytes).hexdigest(),
            "allowlisted_columns": list(ALLOWLIST),
        },
        "planned_events": COHORT_SIZE,
        "selected_events": selected,
        "selected_event_count": len(selected),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument("--freeze-commit", required=True)
    parser.add_argument("--freeze-committed-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(
        args.catalog,
        source_url=args.source_url,
        source_version=args.source_version,
        retrieved_at=args.retrieved_at,
        freeze_commit=args.freeze_commit,
        freeze_committed_at=args.freeze_committed_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{manifest['state']} {manifest['selected_event_count']}/{manifest['planned_events']}")


if __name__ == "__main__":
    main()
