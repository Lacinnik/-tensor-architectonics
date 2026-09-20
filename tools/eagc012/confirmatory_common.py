"""Shared fail-closed helpers for the prospective EAGC-012 ICME protocol."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROTOCOL_ID = "TZAR-RESEARCH-EAGC-012-CONFIRMATORY-ICME"
PROTOCOL_VERSION = "1.1.1-prospective"
PROTOCOL_PATH = Path("tools/eagc012/confirmatory_icme_protocol_v1.1.1.json")
REGISTRY_PATH = Path("tools/eagc012/confirmatory_protocol_registry.json")
MODEL_PATH = Path("tools/eagc012/frozen/confirmatory-icme-v1.1-model.json")
BOOTSTRAP_PATH = Path(
    "tools/eagc012/frozen/confirmatory-icme-v1.1-bootstrap-indices.bin"
)
MANIFEST_PATH = Path("tools/eagc012/frozen/confirmatory-icme-v1.1.1-events.json")
AUTHORIZATION_PATH = Path(
    "tools/eagc012/frozen/confirmatory-icme-v1.1.1-target-authorization.json"
)

ALLOWLIST = ("icmecat_id", "sc_insitu", "icme_start_time", "mo_end_time")
COHORT_SIZE = 20
CUTOFF_MINUTES = 720
MINIMUM_TARGET_MINUTES = 720
OMNI_BASE = "https://spdf.gsfc.nasa.gov/pub/data/omni/high_res_omni/monthly_1min"
SOURCE_PREFIX = (
    "https://helioforecast.space/static/sync/icmecat/"
    "HELIO4CAST_ICMECAT_v"
)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_FORBIDDEN_MANIFEST_KEYS = {
    "dst",
    "symh",
    "sym_h",
    "sym-h",
    "symh_min",
    "sym_h_min",
    "sym-h-min",
}


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


def require_ancestor(root: Path, ancestor: str, descendant: str) -> None:
    if ancestor == descendant:
        raise ValueError("authorization and manifest must use different commits")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError("manifest commit is not an ancestor of authorization commit")


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} is not a sha256 digest")
    return value


def version_tuple(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)", value)
    if match is None:
        raise ValueError(f"invalid ICMECAT version: {value}")
    return tuple(map(int, match.groups()))


def official_catalog_url(version: str) -> str:
    major, minor = version_tuple(version)
    return f"{SOURCE_PREFIX}{major}{minor}.csv"


def months_for(start: datetime, end: datetime) -> list[str]:
    if end <= start:
        raise ValueError("event window must have positive duration")
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


def _forbid_target_keys(value: Any, *, path: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in _FORBIDDEN_MANIFEST_KEYS:
                raise ValueError(f"forbidden target field in {path}: {key}")
            _forbid_target_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _forbid_target_keys(child, path=f"{path}[{index}]")


def _require_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{label} schema mismatch; missing={missing}, extra={extra}")


def _validate_freeze(value: Any, expected: dict[str, str]) -> None:
    if value != expected:
        raise ValueError("protocol freeze mismatch")
    _require_keys(value, {"commit", "committed_at", "protocol_sha256"}, "freeze")
    if not re.fullmatch(r"[0-9a-f]{40}", value["commit"]):
        raise ValueError("freeze commit is invalid")
    utc(value["committed_at"])
    require_sha256(value["protocol_sha256"], "freeze protocol_sha256")


def _overlaps(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return utc(left["icme_start_time"]) < utc(right["mo_end_time"]) and utc(
        right["icme_start_time"]
    ) < utc(left["mo_end_time"])


def validate_manifest(
    manifest: dict[str, Any],
    protocol_anchor: dict[str, str],
    *,
    require_complete: bool = False,
) -> None:
    allowed_top = {
        "protocol_id",
        "protocol_version",
        "state",
        "target_access_permitted",
        "freeze",
        "snapshot_history",
        "event_decisions",
        "planned_events",
        "selected_events",
        "selected_event_count",
        "hold_reasons",
    }
    extra = set(manifest) - (allowed_top | {"parent_manifest"})
    missing = allowed_top - set(manifest)
    if extra or missing:
        raise ValueError(
            f"manifest schema mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    _forbid_target_keys(manifest)
    if manifest["protocol_id"] != PROTOCOL_ID:
        raise ValueError("manifest protocol_id mismatch")
    if manifest["protocol_version"] != PROTOCOL_VERSION:
        raise ValueError("manifest protocol_version mismatch")
    if manifest["target_access_permitted"] is not False:
        raise ValueError("manifest cannot authorize target access")
    _validate_freeze(manifest["freeze"], protocol_anchor)
    if manifest["planned_events"] != COHORT_SIZE:
        raise ValueError("manifest planned_events mismatch")
    if not isinstance(manifest["hold_reasons"], list) or any(
        not isinstance(item, str) or not item for item in manifest["hold_reasons"]
    ):
        raise ValueError("manifest hold_reasons are invalid")

    history = manifest["snapshot_history"]
    if not isinstance(history, list):
        raise ValueError("manifest snapshot_history is invalid")
    versions: list[str] = []
    frozen_at = utc(protocol_anchor["committed_at"])
    for index, receipt in enumerate(history):
        if not isinstance(receipt, dict):
            raise ValueError("snapshot receipt is not an object")
        _require_keys(
            receipt,
            {
                "source_url",
                "source_version",
                "retrieved_at",
                "source_sha256",
                "projected_rows_sha256",
                "allowlisted_columns",
            },
            f"snapshot_history[{index}]",
        )
        version = receipt["source_version"]
        if receipt["source_url"] != official_catalog_url(version):
            raise ValueError("snapshot source URL is not canonical")
        if utc(receipt["retrieved_at"]) <= frozen_at:
            raise ValueError("snapshot retrieval does not follow protocol freeze")
        require_sha256(receipt["source_sha256"], "snapshot source_sha256")
        require_sha256(
            receipt["projected_rows_sha256"], "snapshot projected_rows_sha256"
        )
        if receipt["allowlisted_columns"] != list(ALLOWLIST):
            raise ValueError("snapshot allowlist mismatch")
        versions.append(version)
    if versions != sorted(set(versions), key=version_tuple):
        raise ValueError("snapshot versions are not unique semantic order")

    decisions = manifest["event_decisions"]
    selected = manifest["selected_events"]
    if not isinstance(decisions, list) or not isinstance(selected, list):
        raise ValueError("manifest event collections are invalid")
    decision_ids: set[str] = set()
    selected_from_decisions: list[dict[str, Any]] = []
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            raise ValueError("event decision is not an object")
        _require_keys(
            decision,
            {"icmecat_id", "first_seen_version", "catalog_row", "decision"},
            f"event_decisions[{index}]",
        )
        row = decision["catalog_row"]
        if not isinstance(row, dict):
            raise ValueError("catalog_row is not an object")
        _require_keys(row, set(ALLOWLIST), f"event_decisions[{index}].catalog_row")
        identifier = decision["icmecat_id"]
        if not identifier or identifier != row["icmecat_id"]:
            raise ValueError("event decision identity mismatch")
        if identifier in decision_ids:
            raise ValueError("duplicate event decision identity")
        decision_ids.add(identifier)
        if row["sc_insitu"] != "Wind":
            raise ValueError("manifest contains a non-Wind event decision")
        start = utc(row["icme_start_time"], whole_minute=True)
        end = utc(row["mo_end_time"], whole_minute=True)
        if start <= frozen_at:
            raise ValueError("manifest contains a pre-freeze event")
        if decision["first_seen_version"] not in versions:
            raise ValueError("event first_seen_version lacks a snapshot receipt")
        if decision["decision"] not in {
            "SELECT",
            "SKIP-TARGET-WINDOW-TOO-SHORT",
            "SKIP-OVERLAP",
        }:
            raise ValueError("unknown event decision")
        if decision["decision"] == "SELECT":
            if end - (start + timedelta(minutes=CUTOFF_MINUTES)) < timedelta(
                minutes=MINIMUM_TARGET_MINUTES
            ):
                raise ValueError("selected event target window is too short")
            if any(_overlaps(row, prior) for prior in selected_from_decisions):
                raise ValueError("selected event overlaps an earlier selection")
            selected_from_decisions.append(
                {
                    "icmecat_id": identifier,
                    "sc_insitu": "Wind",
                    "icme_start_time": row["icme_start_time"],
                    "cutoff": iso(start + timedelta(minutes=CUTOFF_MINUTES)),
                    "mo_end_time": row["mo_end_time"],
                    "first_seen_version": decision["first_seen_version"],
                }
            )
        elif decision["decision"] == "SKIP-TARGET-WINDOW-TOO-SHORT" and end - (
            start + timedelta(minutes=CUTOFF_MINUTES)
        ) >= timedelta(minutes=MINIMUM_TARGET_MINUTES):
            raise ValueError("target-window skip is inconsistent")
        elif decision["decision"] == "SKIP-OVERLAP" and not any(
            _overlaps(row, prior) for prior in selected_from_decisions
        ):
            raise ValueError("overlap skip is inconsistent")

    if selected != selected_from_decisions:
        raise ValueError("selected_events do not equal SELECT decisions")
    if manifest["selected_event_count"] != len(selected) or len(selected) > COHORT_SIZE:
        raise ValueError("manifest selected event count mismatch")
    order = [(utc(item["icme_start_time"]), item["icmecat_id"]) for item in selected]
    if order != sorted(order):
        raise ValueError("selected event order is not canonical")
    for index, event in enumerate(selected):
        _require_keys(
            event,
            {
                "icmecat_id",
                "sc_insitu",
                "icme_start_time",
                "cutoff",
                "mo_end_time",
                "first_seen_version",
            },
            f"selected_events[{index}]",
        )
        start = utc(event["icme_start_time"], whole_minute=True)
        cutoff = utc(event["cutoff"], whole_minute=True)
        end = utc(event["mo_end_time"], whole_minute=True)
        if cutoff != start + timedelta(minutes=CUTOFF_MINUTES):
            raise ValueError("selected event cutoff mismatch")
        if end - cutoff < timedelta(minutes=MINIMUM_TARGET_MINUTES):
            raise ValueError("selected event target window is too short")
        if any(_overlaps(event, prior) for prior in selected[:index]):
            raise ValueError("selected event windows overlap")

    state = manifest["state"]
    if state == "MANIFEST-CANDIDATE":
        if len(selected) != COHORT_SIZE or manifest["hold_reasons"]:
            raise ValueError("complete manifest state is inconsistent")
    elif state == "OPEN-ACCRUAL":
        if len(selected) >= COHORT_SIZE or manifest["hold_reasons"]:
            raise ValueError("open manifest state is inconsistent")
    elif isinstance(state, str) and state.startswith("HOLD-"):
        if not manifest["hold_reasons"]:
            raise ValueError("HOLD manifest lacks a reason")
    else:
        raise ValueError("manifest state is invalid")
    if require_complete and state != "MANIFEST-CANDIDATE":
        raise ValueError("manifest is not complete")

    if "parent_manifest" in manifest:
        parent = manifest["parent_manifest"]
        if not isinstance(parent, dict):
            raise ValueError("parent_manifest is not an object")
        _require_keys(
            parent,
            {"path", "commit", "committed_at", "sha256"},
            "parent_manifest",
        )
        if parent["path"] != MANIFEST_PATH.as_posix():
            raise ValueError("parent manifest path mismatch")
        if not re.fullmatch(r"[0-9a-f]{40}", parent["commit"]):
            raise ValueError("parent manifest commit is invalid")
        utc(parent["committed_at"])
        require_sha256(parent["sha256"], "parent manifest sha256")


def validate_authorization_document(
    authorization: dict[str, Any],
    *,
    manifest_evidence: dict[str, str],
    protocol_anchor: dict[str, str],
) -> None:
    _require_keys(
        authorization,
        {
            "protocol_id",
            "protocol_version",
            "state",
            "target_access_permitted",
            "manifest",
            "protocol_freeze",
            "activation_rule",
        },
        "authorization",
    )
    if authorization["protocol_id"] != PROTOCOL_ID:
        raise ValueError("authorization protocol_id mismatch")
    if authorization["protocol_version"] != PROTOCOL_VERSION:
        raise ValueError("authorization protocol_version mismatch")
    if authorization["state"] != "TARGET-AUTHORIZATION-CANDIDATE":
        raise ValueError("authorization state mismatch")
    if authorization["target_access_permitted"] is not False:
        raise ValueError("authorization file must be inert until committed")
    expected_rule = (
        "Target access is permitted only after this exact authorization "
        "file is committed. The data preparer resolves and verifies that "
        "earlier commit before making any OMNI request."
    )
    if authorization["activation_rule"] != expected_rule:
        raise ValueError("authorization activation rule mismatch")
    _require_keys(
        authorization["manifest"],
        {"path", "sha256", "commit", "committed_at"},
        "authorization.manifest",
    )
    expected_manifest = {
        "path": MANIFEST_PATH.as_posix(),
        "sha256": manifest_evidence["sha256"],
        "commit": manifest_evidence["commit"],
        "committed_at": manifest_evidence["committed_at"],
    }
    if authorization["manifest"] != expected_manifest:
        raise ValueError("authorization does not bind exact manifest evidence")
    _validate_freeze(authorization["protocol_freeze"], protocol_anchor)


def validate_parent_manifest_evidence(
    root: Path,
    manifest: dict[str, Any],
    current_evidence: dict[str, str],
) -> None:
    parent = manifest.get("parent_manifest")
    if parent is None:
        return
    parent_path = Path(parent["path"])
    raw = file_at_commit(root, parent["commit"], parent_path)
    if sha256_bytes(raw) != parent["sha256"]:
        raise ValueError("parent manifest committed bytes mismatch")
    if iso(commit_timestamp(root, parent["commit"])) != parent["committed_at"]:
        raise ValueError("parent manifest committed_at mismatch")
    require_ancestor(root, parent["commit"], current_evidence["commit"])


def validate_source_receipts(
    summary: dict[str, Any],
    manifest: dict[str, Any],
    authorization_evidence: dict[str, str],
) -> None:
    _require_keys(
        summary,
        {
            "protocol_id",
            "protocol_version",
            "manifest_sha256",
            "manifest_commit",
            "authorization_sha256",
            "authorization_commit",
            "retrieval_completed_at",
            "source_files",
            "events",
        },
        "summary",
    )
    if summary["protocol_id"] != PROTOCOL_ID:
        raise ValueError("summary protocol_id mismatch")
    if summary["protocol_version"] != PROTOCOL_VERSION:
        raise ValueError("summary protocol_version mismatch")
    completed = utc(summary["retrieval_completed_at"])
    authorized_at = utc(authorization_evidence["committed_at"])
    if completed <= authorized_at:
        raise ValueError("target retrieval did not follow authorization commit")
    required_months = sorted(
        {
            month
            for event in manifest["selected_events"]
            for month in months_for(
                utc(event["icme_start_time"]), utc(event["mo_end_time"])
            )
        }
    )
    sources = summary.get("source_files")
    if not isinstance(sources, dict) or sorted(sources) != required_months:
        raise ValueError("target source month set mismatch")
    for month in required_months:
        receipt = sources[month]
        if not isinstance(receipt, dict):
            raise ValueError("target source receipt is not an object")
        _require_keys(
            receipt,
            {"url", "retrieved_at", "sha256", "size_bytes"},
            f"source_files.{month}",
        )
        expected_url = f"{OMNI_BASE}/omni_min{month}.asc"
        if receipt["url"] != expected_url:
            raise ValueError("target source URL mismatch")
        retrieved = utc(receipt["retrieved_at"])
        if retrieved <= authorized_at or retrieved > completed:
            raise ValueError("target source retrieval chronology mismatch")
        require_sha256(receipt["sha256"], "target source sha256")
        if not isinstance(receipt["size_bytes"], int) or receipt["size_bytes"] <= 0:
            raise ValueError("target source size is invalid")
