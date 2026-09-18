#!/usr/bin/env python3
"""Create a commit-required target authorization candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from confirmatory_common import (
    AUTHORIZATION_PATH,
    MANIFEST_PATH,
    PROTOCOL_ID,
    PROTOCOL_VERSION,
    repository_root,
    require_exact_committed_file,
    sha256_file,
    verify_protocol_anchor,
)


def build_authorization(
    manifest: dict[str, Any],
    *,
    manifest_path: Path,
    manifest_evidence: dict[str, str],
    protocol_anchor: dict[str, str],
) -> dict[str, Any]:
    if manifest.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("manifest protocol_id mismatch")
    if manifest.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("manifest protocol_version mismatch")
    if manifest.get("state") != "MANIFEST-CANDIDATE":
        raise ValueError("manifest is not complete")
    if manifest.get("target_access_permitted") is not False:
        raise ValueError("manifest cannot authorize target access")
    if manifest.get("selected_event_count") != 20:
        raise ValueError("manifest must contain exactly 20 selected events")
    if len(manifest.get("selected_events", [])) != 20:
        raise ValueError("manifest selected event list is incomplete")
    if manifest.get("freeze") != protocol_anchor:
        raise ValueError("manifest protocol freeze mismatch")
    if manifest.get("hold_reasons"):
        raise ValueError("manifest has unresolved HOLD reasons")
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
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    relative_manifest = manifest_path.relative_to(root)
    evidence = require_exact_committed_file(root, relative_manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if evidence["sha256"] != sha256_file(manifest_path):
        raise ValueError("manifest changed after commit evidence resolution")
    authorization = build_authorization(
        manifest,
        manifest_path=relative_manifest,
        manifest_evidence=evidence,
        protocol_anchor=verify_protocol_anchor(root),
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
