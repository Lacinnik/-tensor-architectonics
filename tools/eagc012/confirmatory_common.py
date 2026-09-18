"""Shared fail-closed helpers for the prospective EAGC-012 ICME protocol."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROTOCOL_ID = "TZAR-RESEARCH-EAGC-012-CONFIRMATORY-ICME"
PROTOCOL_VERSION = "1.1.0-prospective"
PROTOCOL_PATH = Path("tools/eagc012/confirmatory_icme_protocol_v1.1.0.json")
REGISTRY_PATH = Path("tools/eagc012/confirmatory_protocol_registry.json")
MODEL_PATH = Path("tools/eagc012/frozen/confirmatory-icme-v1.1-model.json")
BOOTSTRAP_PATH = Path(
    "tools/eagc012/frozen/confirmatory-icme-v1.1-bootstrap-indices.bin"
)
MANIFEST_PATH = Path("tools/eagc012/frozen/confirmatory-icme-v1.1-events.json")
AUTHORIZATION_PATH = Path(
    "tools/eagc012/frozen/confirmatory-icme-v1.1-target-authorization.json"
)


def utc(value: str, *, whole_minute: bool = False) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone: {value}")
    parsed = parsed.astimezone(timezone.utc)
    if whole_minute and (parsed.second or parsed.microsecond):
        raise ValueError(f"timestamp is not a whole minute: {value}")
    return parsed


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repository_root(start: Path | None = None) -> Path:
    working = (start or Path.cwd()).resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=working,
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def git(root: Path, *arguments: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=False,
    )
    if check and result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"git {' '.join(arguments)} failed: {message}")
    return result.stdout.decode("utf-8", errors="strict")


def commit_timestamp(root: Path, commit: str) -> datetime:
    return utc(git(root, "show", "-s", "--format=%cI", commit).strip())


def file_at_commit(root: Path, commit: str, path: Path) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path.as_posix()}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(f"{path.as_posix()} is absent at {commit}")
    return result.stdout


def path_commits(root: Path, path: Path) -> list[str]:
    output = git(
        root,
        "log",
        "--reverse",
        "--format=%H",
        "--follow",
        "--",
        path.as_posix(),
    )
    return [line for line in output.splitlines() if line]


def resolve_protocol_anchor(
    root: Path,
    *,
    path: Path = PROTOCOL_PATH,
    protocol_id: str = PROTOCOL_ID,
    protocol_version: str = PROTOCOL_VERSION,
) -> dict[str, str]:
    for commit in path_commits(root, path):
        try:
            raw = file_at_commit(root, commit, path)
            value = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            continue
        if (
            value.get("protocol_id") == protocol_id
            and value.get("protocol_version") == protocol_version
        ):
            return {
                "commit": commit,
                "committed_at": iso(commit_timestamp(root, commit)),
                "protocol_sha256": sha256_bytes(raw),
            }
    raise ValueError(
        f"no introducing commit for {protocol_id} {protocol_version} at {path}"
    )


def verify_protocol_anchor(root: Path, path: Path = PROTOCOL_PATH) -> dict[str, str]:
    anchor = resolve_protocol_anchor(root, path=path)
    current = (root / path).read_bytes()
    if sha256_bytes(current) != anchor["protocol_sha256"]:
        raise ValueError("current protocol bytes differ from the introducing commit")
    return anchor


def first_commit_with_file_hash(
    root: Path, path: Path, expected_sha256: str
) -> dict[str, str]:
    for commit in path_commits(root, path):
        try:
            raw = file_at_commit(root, commit, path)
        except ValueError:
            continue
        if sha256_bytes(raw) == expected_sha256:
            return {
                "commit": commit,
                "committed_at": iso(commit_timestamp(root, commit)),
                "sha256": expected_sha256,
            }
    raise ValueError(
        f"no committed {path.as_posix()} has sha256 {expected_sha256}"
    )


def require_exact_committed_file(
    root: Path, path: Path
) -> dict[str, str]:
    if not (root / path).is_file():
        raise ValueError(f"missing file: {path.as_posix()}")
    digest = sha256_file(root / path)
    return first_commit_with_file_hash(root, path, digest)
