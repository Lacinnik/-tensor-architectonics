#!/usr/bin/env python3
"""Append-only, target-blind accrual for EAGC-012 ICME v1.1."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from confirmatory_common import (
    MANIFEST_PATH,
    PROTOCOL_ID,
    PROTOCOL_VERSION,
    canonical_json_bytes,
    iso,
    repository_root,
    require_exact_committed_file,
    sha256_bytes,
    utc,
    verify_protocol_anchor,
)


ALLOWLIST = ("icmecat_id", "sc_insitu", "icme_start_time", "mo_end_time")
COHORT_SIZE = 20
CUTOFF_MINUTES = 720
MINIMUM_TARGET_MINUTES = 720
LANDING_URL = "https://helioforecast.space/icmecat"
SOURCE_PREFIX = (
    "https://helioforecast.space/static/sync/icmecat/"
    "HELIO4CAST_ICMECAT_v"
)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value)


def version_tuple(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)", value)
    if match is None:
        raise ValueError(f"invalid ICMECAT version: {value}")
    major, minor = map(int, match.groups())
    return major, minor


def official_url(version: str) -> str:
    major, minor = version_tuple(version)
    return f"{SOURCE_PREFIX}{major}{minor}.csv"


def version_from_url(url: str) -> str:
    match = re.fullmatch(re.escape(SOURCE_PREFIX) + r"(\d)(\d+)\.csv", url)
    if match is None:
        raise ValueError(f"not an official versioned ICMECAT URL: {url}")
    return f"{int(match.group(1))}.{int(match.group(2))}"


def discover_official_snapshots(html: str) -> list[tuple[str, str]]:
    parser = LinkParser()
    parser.feed(html)
    found: dict[str, str] = {}
    for link in parser.links:
        absolute = urllib.parse.urljoin(LANDING_URL, link)
        try:
            version = version_from_url(absolute)
        except ValueError:
            continue
        if version_tuple(version) >= (2, 3):
            found[version] = absolute
    if not found:
        raise ValueError("landing page exposes no official ICMECAT snapshot")
    return sorted(found.items(), key=lambda item: version_tuple(item[0]))


def parse_projection(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    missing = [name for name in ALLOWLIST if name not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"catalog missing allowlisted columns: {', '.join(missing)}")
    return [
        {name: (row[name] or "").strip() for name in ALLOWLIST}
        for row in reader
    ]


def normalized_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "icmecat_id": row["icmecat_id"],
        "sc_insitu": row["sc_insitu"],
        "icme_start_time": iso(utc(row["icme_start_time"], whole_minute=True)),
        "mo_end_time": iso(utc(row["mo_end_time"], whole_minute=True)),
    }


def overlaps(left: dict[str, str], right: dict[str, str]) -> bool:
    return utc(left["icme_start_time"]) < utc(right["mo_end_time"]) and utc(
        right["icme_start_time"]
    ) < utc(left["mo_end_time"])


def new_manifest(freeze: dict[str, str]) -> dict[str, Any]:
    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "state": "OPEN-ACCRUAL",
        "target_access_permitted": False,
        "freeze": freeze,
        "snapshot_history": [],
        "event_decisions": [],
        "planned_events": COHORT_SIZE,
        "selected_events": [],
        "selected_event_count": 0,
        "hold_reasons": [],
    }


def validate_previous(previous: dict[str, Any], freeze: dict[str, str]) -> None:
    if previous.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("previous manifest protocol_id mismatch")
    if previous.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("previous manifest protocol_version mismatch")
    if previous.get("freeze") != freeze:
        raise ValueError("previous manifest freeze anchor mismatch")
    if previous.get("target_access_permitted") is not False:
        raise ValueError("accrual manifest must never permit target access")
    selected = previous.get("selected_events")
    if not isinstance(selected, list) or len(selected) > COHORT_SIZE:
        raise ValueError("invalid previous selected_events")
    if previous.get("selected_event_count") != len(selected):
        raise ValueError("previous selected_event_count mismatch")


def apply_snapshot(
    previous: dict[str, Any] | None,
    *,
    raw: bytes,
    source_url: str,
    source_version: str,
    retrieved_at: str,
    freeze: dict[str, str],
) -> dict[str, Any]:
    if source_url != official_url(source_version):
        raise ValueError("source URL does not exactly match source_version")
    retrieved = utc(retrieved_at)
    frozen = utc(freeze["committed_at"])
    if retrieved <= frozen:
        raise ValueError("catalog snapshot must be retrieved after protocol freeze")

    result = deepcopy(previous) if previous is not None else new_manifest(freeze)
    validate_previous(result, freeze)
    if result["state"] == "MANIFEST-CANDIDATE":
        raise ValueError("complete manifest is immutable")
    if result["state"].startswith("HOLD"):
        raise ValueError("HOLD manifest cannot continue accrual")

    raw_hash = sha256_bytes(raw)
    projection = [normalized_row(row) for row in parse_projection(raw)]
    projection_hash = sha256_bytes(canonical_json_bytes(projection))
    history = result["snapshot_history"]
    for recorded in history:
        if recorded["source_version"] == source_version:
            if recorded["source_sha256"] != raw_hash:
                result["state"] = "HOLD-SOURCE-MUTATION"
                result["hold_reasons"] = [
                    f"official URL bytes changed for ICMECAT {source_version}"
                ]
            return result
    if history and version_tuple(source_version) <= version_tuple(
        history[-1]["source_version"]
    ):
        raise ValueError("snapshots must be processed in increasing version order")

    snapshot = {
        "source_url": source_url,
        "source_version": source_version,
        "retrieved_at": iso(retrieved),
        "source_sha256": raw_hash,
        "projected_rows_sha256": projection_hash,
        "allowlisted_columns": list(ALLOWLIST),
    }
    history.append(snapshot)

    existing = {
        item["icmecat_id"]: item for item in result["event_decisions"]
    }
    rows_by_id: dict[str, dict[str, str]] = {}
    for row in projection:
        if row["sc_insitu"] != "Wind":
            continue
        identifier = row["icmecat_id"]
        if not identifier:
            result["state"] = "HOLD-CATALOG-INVARIANT"
            result["hold_reasons"] = ["post-freeze Wind row has empty icmecat_id"]
            return result
        if identifier in rows_by_id:
            result["state"] = "HOLD-CATALOG-INVARIANT"
            result["hold_reasons"] = [f"duplicate icmecat_id: {identifier}"]
            return result
        rows_by_id[identifier] = row

    for identifier, decision in existing.items():
        current = rows_by_id.get(identifier)
        if current is None:
            result["state"] = "HOLD-CATALOG-REVISION"
            result["hold_reasons"] = [
                f"catalog row disappeared after first decision: {identifier}"
            ]
            return result
        if decision["catalog_row"] != current:
            result["state"] = "HOLD-CATALOG-REVISION"
            result["hold_reasons"] = [
                f"catalog row changed after first decision: {identifier}"
            ]
            return result

    unseen = [row for key, row in rows_by_id.items() if key not in existing]
    unseen.sort(key=lambda row: (utc(row["icme_start_time"]), row["icmecat_id"]))
    selected = result["selected_events"]
    for row in unseen:
        start = utc(row["icme_start_time"], whole_minute=True)
        end = utc(row["mo_end_time"], whole_minute=True)
        if start <= frozen:
            continue
        decision = {
            "icmecat_id": row["icmecat_id"],
            "first_seen_version": source_version,
            "catalog_row": row,
            "decision": "",
        }
        if end - (start + timedelta(minutes=CUTOFF_MINUTES)) < timedelta(
            minutes=MINIMUM_TARGET_MINUTES
        ):
            decision["decision"] = "SKIP-TARGET-WINDOW-TOO-SHORT"
        elif any(overlaps(row, prior) for prior in selected):
            decision["decision"] = "SKIP-OVERLAP"
        elif len(selected) < COHORT_SIZE:
            decision["decision"] = "SELECT"
            selected.append(
                {
                    "icmecat_id": row["icmecat_id"],
                    "sc_insitu": "Wind",
                    "icme_start_time": row["icme_start_time"],
                    "cutoff": iso(start + timedelta(minutes=CUTOFF_MINUTES)),
                    "mo_end_time": row["mo_end_time"],
                    "first_seen_version": source_version,
                }
            )
        else:
            break
        result["event_decisions"].append(decision)
        if len(selected) == COHORT_SIZE:
            break

    result["selected_event_count"] = len(selected)
    result["state"] = (
        "MANIFEST-CANDIDATE" if len(selected) == COHORT_SIZE else "OPEN-ACCRUAL"
    )
    result["hold_reasons"] = []
    return result


def fetch(url: str) -> tuple[bytes, str]:
    with urllib.request.urlopen(url, timeout=120) as response:
        raw = response.read()
    return raw, iso(datetime.now(timezone.utc))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-manifest", type=Path)
    parser.add_argument("--output", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args()

    root = repository_root(Path(__file__).parent)
    freeze = verify_protocol_anchor(root)
    previous_path = args.previous_manifest
    if previous_path is None and args.output.is_file():
        previous_path = args.output
    previous_evidence = None
    if previous_path:
        if not previous_path.is_absolute():
            previous_path = root / previous_path
        previous_evidence = require_exact_committed_file(
            root, previous_path.relative_to(root)
        )
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
    else:
        previous = None

    landing_raw, _ = fetch(LANDING_URL)
    snapshots = discover_official_snapshots(landing_raw.decode("utf-8"))
    result = previous
    processed = {
        item["source_version"]
        for item in (previous or {}).get("snapshot_history", [])
    }
    for version, url in snapshots:
        raw, retrieved_at = fetch(url)
        if version in processed:
            check = apply_snapshot(
                result,
                raw=raw,
                source_url=url,
                source_version=version,
                retrieved_at=retrieved_at,
                freeze=freeze,
            )
            if check["state"].startswith("HOLD"):
                result = check
                break
            continue
        result = apply_snapshot(
            result,
            raw=raw,
            source_url=url,
            source_version=version,
            retrieved_at=retrieved_at,
            freeze=freeze,
        )
        if result["state"] != "OPEN-ACCRUAL":
            break

    if result is None:
        result = new_manifest(freeze)
    if previous is not None and previous_evidence is not None and result != previous:
        result["parent_manifest"] = {
            "path": previous_path.relative_to(root).as_posix(),
            **previous_evidence,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"{result['state']} "
        f"{result['selected_event_count']}/{result['planned_events']}"
    )


if __name__ == "__main__":
    main()
