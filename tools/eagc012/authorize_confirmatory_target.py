#!/usr/bin/env python3
"""Create a commit-required target authorization candidate."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any

from confirmatory_common import (
    AUTHORIZATION_PATH,
    MANIFEST_PATH,
    PROTOCOL_ID,
    PROTOCOL_VERSION,
    repository_root,
    require_ancestor,
    require_exact_committed_file,
    sha256_file,
    validate_manifest,
    validate_parent_manifest_evidence,
    verify_protocol_anchor,
)


def build_authorization(
    manifest: dict[str, Any],
    *,
    manifest_path: Path,
    manifest_evidence: dict[str, str],
    protocol_anchor: dict[str, str],
) -> dict[str, Any]:
    validate_manifest(manifest, protocol_anchor, require_complete=True)
    if manifest_path != MANIFEST_PATH:
        raise ValueError("authorization requires the canonical manifest path")
    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "state": "TARGET-AUTHORIZATION-CANDIDATE",
        "target_access_permitted": False,
        "manifest": {
            "path": manifest_path.as_posix(),
            "sha256": manifest_evidence["sha256"],
            "commit": manifest_evidence["commit"],
            "committed_at": manifest_evidence["committed_at"],
        },
        "protocol_freeze": protocol_anchor,
        "activation_rule": (
            "Target access is permitted only after this exact authorization "
            "file is committed. The data preparer resolves and verifies that "
            "earlier commit before making any OMNI request."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--output", type=Path, default=AUTHORIZATION_PATH)
    args = parser.parse_args()

    root = repository_root(Path(__file__).parent)
    from validate_confirmatory_protocol import load_and_validate

    load_and_validate(root)
    protocol_anchor = verify_protocol_anchor(root)
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    relative_manifest = manifest_path.relative_to(root)
    evidence = require_exact_committed_file(root, relative_manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if evidence["sha256"] != sha256_file(manifest_path):
        raise ValueError("manifest changed after commit evidence resolution")
    validate_manifest(manifest, protocol_anchor, require_complete=True)
    require_ancestor(root, protocol_anchor["commit"], evidence["commit"])
    validate_parent_manifest_evidence(root, manifest, evidence)

    from accrue_confirmatory_cohort import (
        LANDING_URL,
        apply_snapshot,
        discover_official_snapshots,
    )

    with urllib.request.urlopen(LANDING_URL, timeout=120) as response:
        discovered = discover_official_snapshots(response.read().decode("utf-8"))
    history = manifest["snapshot_history"]
    if not history:
        raise ValueError("complete manifest lacks snapshot history")
    last_version = history[-1]["source_version"]
    expected_prefix = [
        (version, url)
        for version, url in discovered
        if version in {item["source_version"] for item in history}
        or tuple(map(int, version.split(".")))
        <= tuple(map(int, last_version.split(".")))
    ]
    recorded = [(item["source_version"], item["source_url"]) for item in history]
    if expected_prefix != recorded:
        raise ValueError("manifest snapshot history omits or rewrites official versions")
    replay = None
    for receipt in history:
        with urllib.request.urlopen(receipt["source_url"], timeout=120) as response:
            raw = response.read()
        replay = apply_snapshot(
            replay,
            raw=raw,
            source_url=receipt["source_url"],
            source_version=receipt["source_version"],
            retrieved_at=receipt["retrieved_at"],
            freeze=protocol_anchor,
        )
    comparable = {key: value for key, value in manifest.items() if key != "parent_manifest"}
    if replay != comparable:
        raise ValueError("manifest does not replay from official target-blind sources")
    authorization = build_authorization(
        manifest,
        manifest_path=relative_manifest,
        manifest_evidence=evidence,
        protocol_anchor=protocol_anchor,
    )
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(authorization, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("TARGET-AUTHORIZATION-CANDIDATE commit-before-access")


if __name__ == "__main__":
    main()
