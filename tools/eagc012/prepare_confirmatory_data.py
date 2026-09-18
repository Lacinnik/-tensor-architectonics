#!/usr/bin/env python3
"""Retrieve and prepare prospective OMNI data only after committed authorization."""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from confirmatory_common import (
    AUTHORIZATION_PATH,
    MANIFEST_PATH,
    MODEL_PATH,
    PROTOCOL_ID,
    PROTOCOL_VERSION,
    iso,
    repository_root,
    require_exact_committed_file,
    sha256_bytes,
    sha256_file,
    utc,
    verify_protocol_anchor,
)
from run_gate import (
    feature_vector,
    minute_grid,
    parse,
    quality_result,
    target_after_cutoff,
)


OMNI_BASE = "https://spdf.gsfc.nasa.gov/pub/data/omni/high_res_omni/monthly_1min"


def months_for(start: datetime, end: datetime) -> list[str]:
    months: list[str] = []
    cursor = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last = end - timedelta(minutes=1)
    while (cursor.year, cursor.month) <= (last.year, last.month):
        months.append(cursor.strftime("%Y%m"))
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return months


def require_ancestor(root: Path, ancestor: str, descendant: str) -> None:
    if ancestor == descendant:
        raise ValueError("authorization and manifest must use different commits")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        check=False,
    )
    if result.returncode:
        raise ValueError("manifest commit is not an ancestor of authorization commit")


def validate_authorization(
    authorization: dict[str, Any],
    *,
    manifest_hash: str,
    protocol_anchor: dict[str, str],
    authorization_evidence: dict[str, str],
) -> None:
    if authorization.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("authorization protocol_id mismatch")
    if authorization.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("authorization protocol_version mismatch")
    if authorization.get("state") != "TARGET-AUTHORIZATION-CANDIDATE":
        raise ValueError("authorization state mismatch")
    if authorization.get("target_access_permitted") is not False:
        raise ValueError("authorization file must be inert until committed")
    if authorization.get("manifest", {}).get("sha256") != manifest_hash:
        raise ValueError("authorization manifest hash mismatch")
    if authorization.get("protocol_freeze") != protocol_anchor:
        raise ValueError("authorization protocol freeze mismatch")
    if utc(authorization_evidence["committed_at"]) >= datetime.now(timezone.utc):
        raise ValueError("authorization commit must predate target retrieval")


def fetch_month(month: str, raw_dir: Path) -> dict[str, Any]:
    url = f"{OMNI_BASE}/omni_min{month}.asc"
    retrieved_at = datetime.now(timezone.utc)
    with urllib.request.urlopen(url, timeout=120) as response:
        raw = response.read()
    destination = raw_dir / f"omni_min{month}.asc"
    destination.write_bytes(raw)
    return {
        "path": destination,
        "url": url,
        "retrieved_at": iso(retrieved_at),
        "sha256": sha256_bytes(raw),
        "size_bytes": len(raw),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--authorization", type=Path, default=AUTHORIZATION_PATH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = repository_root(Path(__file__).parent)
    protocol_anchor = verify_protocol_anchor(root)
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    authorization_path = (
        args.authorization
        if args.authorization.is_absolute()
        else root / args.authorization
    )
    manifest_relative = manifest_path.relative_to(root)
    authorization_relative = authorization_path.relative_to(root)
    manifest_evidence = require_exact_committed_file(root, manifest_relative)
    authorization_evidence = require_exact_committed_file(
        root, authorization_relative
    )
    require_ancestor(
        root, manifest_evidence["commit"], authorization_evidence["commit"]
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    validate_authorization(
        authorization,
        manifest_hash=manifest_evidence["sha256"],
        protocol_anchor=protocol_anchor,
        authorization_evidence=authorization_evidence,
    )
    if manifest.get("state") != "MANIFEST-CANDIDATE":
        raise ValueError("manifest is not ready for target retrieval")
    if manifest.get("selected_event_count") != 20:
        raise ValueError("manifest must contain 20 events")

    model = json.loads((root / MODEL_PATH).read_text(encoding="utf-8"))
    runner_path = root / "tools/eagc012/run_gate.py"
    if sha256_file(runner_path) != model["provenance"]["runner_sha256"]:
        raise ValueError("feature runner differs from frozen model provenance")

    output = args.output if args.output.is_absolute() else root / args.output
    raw_dir = output.parent / f"{output.stem}-raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    required_months = sorted(
        {
            month
            for event in manifest["selected_events"]
            for month in months_for(
                utc(event["icme_start_time"]), utc(event["mo_end_time"])
            )
        }
    )
    sources = {month: fetch_month(month, raw_dir) for month in required_months}

    summaries: list[dict[str, Any]] = []
    for event in manifest["selected_events"]:
        start = utc(event["icme_start_time"])
        cutoff = utc(event["cutoff"])
        end = utc(event["mo_end_time"])
        parsed = []
        monotonic = True
        malformed = 0
        for month in months_for(start, end):
            rows, month_monotonic, _, month_malformed = parse(
                sources[month]["path"], start, end
            )
            parsed.extend(rows)
            monotonic = monotonic and month_monotonic
            malformed += month_malformed
        duplicates = len(parsed) - len({row.t for row in parsed})
        if any(after.t <= before.t for before, after in zip(parsed, parsed[1:])):
            monotonic = False
        rows = minute_grid(parsed, start, end)
        prefix = [row for row in rows if row.t < cutoff]
        target_rows = [row for row in rows if row.t >= cutoff]
        features_all = feature_vector(rows, cutoff, 15)
        features_prefix = feature_vector(prefix, cutoff, 15)
        status, coverage, gaps, target_coverage, target_gaps, failures = quality_result(
            prefix,
            target_rows=target_rows,
            required_fields=["by", "bz", "speed", "pressure", "symh"],
            gap_fields=["by", "bz", "speed", "pressure", "symh"],
            minimum_coverage=0.75,
            maximum_gap=15,
            target_minimum_coverage=0.9,
            monotonic=monotonic,
            duplicates=duplicates,
            prefix_invariant=features_all == features_prefix,
            prefix_features_available=features_prefix is not None,
        )
        summary: dict[str, Any] = {
            "event_id": event["icmecat_id"],
            "quality_status": status,
            "quality_failures": failures,
            "window_start": event["icme_start_time"],
            "forecast_cutoff": event["cutoff"],
            "window_end_exclusive": event["mo_end_time"],
            "coverage": coverage,
            "max_gap_min": gaps,
            "target_coverage": target_coverage,
            "target_max_gap_min": target_gaps,
            "duplicate_timestamps": duplicates,
            "malformed_source_rows": malformed,
            "SYM_H_min": target_after_cutoff(rows, cutoff),
            "source_months": months_for(start, end),
        }
        if features_prefix:
            summary.update(features_prefix)
        summaries.append(summary)

    source_manifest = {
        month: {key: value for key, value in item.items() if key != "path"}
        for month, item in sources.items()
    }
    result = {
        "protocol_id": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "manifest_sha256": manifest_evidence["sha256"],
        "manifest_commit": manifest_evidence["commit"],
        "authorization_sha256": authorization_evidence["sha256"],
        "authorization_commit": authorization_evidence["commit"],
        "retrieval_completed_at": iso(datetime.now(timezone.utc)),
        "source_files": source_manifest,
        "events": summaries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"TARGET-DATA-PREPARED {len(summaries)} events")


if __name__ == "__main__":
    main()
