#!/usr/bin/env python3
"""Retrieve and prepare prospective OMNI data only after committed authorization."""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from confirmatory_common import (
    AUTHORIZATION_PATH,
    MANIFEST_PATH,
    MODEL_PATH,
    OMNI_BASE,
    PROTOCOL_ID,
    PROTOCOL_VERSION,
    iso,
    months_for,
    repository_root,
    require_ancestor,
    require_exact_committed_file,
    sha256_bytes,
    sha256_file,
    utc,
    validate_authorization_document,
    validate_manifest,
    validate_parent_manifest_evidence,
    validate_source_receipts,
    verify_protocol_anchor,
)


def validate_authorization(
    authorization: dict[str, Any],
    *,
    manifest_hash: str,
    protocol_anchor: dict[str, str],
    authorization_evidence: dict[str, str],
) -> None:
    manifest_evidence = {
        "sha256": manifest_hash,
        "commit": authorization.get("manifest", {}).get("commit"),
        "committed_at": authorization.get("manifest", {}).get("committed_at"),
    }
    validate_authorization_document(
        authorization,
        manifest_evidence=manifest_evidence,
        protocol_anchor=protocol_anchor,
    )
    if utc(authorization_evidence["committed_at"]) >= datetime.now(timezone.utc):
        raise ValueError("authorization commit must predate target retrieval")


def fetch_month(month: str, raw_dir: Path) -> dict[str, Any]:
    url = f"{OMNI_BASE}/omni_min{month}.asc"
    with urllib.request.urlopen(url, timeout=120) as response:
        raw = response.read()
    retrieved_at = datetime.now(timezone.utc)
    destination = raw_dir / f"omni_min{month}.asc"
    destination.write_bytes(raw)
    return {
        "path": destination,
        "url": url,
        "retrieved_at": iso(retrieved_at),
        "sha256": sha256_bytes(raw),
        "size_bytes": len(raw),
    }


def build_event_summaries(
    manifest: dict[str, Any], sources: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    from run_gate import (
        feature_vector,
        minute_grid,
        parse,
        quality_result,
        target_after_cutoff,
    )

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
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--authorization", type=Path, default=AUTHORIZATION_PATH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

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
    validate_manifest(manifest, protocol_anchor, require_complete=True)
    require_ancestor(root, protocol_anchor["commit"], manifest_evidence["commit"])
    validate_parent_manifest_evidence(root, manifest, manifest_evidence)
    validate_authorization_document(
        authorization,
        manifest_evidence=manifest_evidence,
        protocol_anchor=protocol_anchor,
    )
    if utc(authorization_evidence["committed_at"]) >= datetime.now(timezone.utc):
        raise ValueError("authorization commit must predate target retrieval")

    model = json.loads((root / MODEL_PATH).read_text(encoding="utf-8"))
    runner_path = root / "tools/eagc012/run_gate.py"
    if sha256_file(runner_path) != model["provenance"]["runner_sha256"]:
        raise ValueError("feature runner differs from frozen model provenance")
    if sha256_file(root / MODEL_PATH) != protocol["model"]["artifact_sha256"]:
        raise ValueError("model artifact differs from protocol")

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

    summaries = build_event_summaries(manifest, sources)

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
    validate_source_receipts(result, manifest, authorization_evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"TARGET-DATA-PREPARED {len(summaries)} events")


if __name__ == "__main__":
    main()
