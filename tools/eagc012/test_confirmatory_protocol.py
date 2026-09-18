import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from accrue_confirmatory_cohort import (
    apply_snapshot,
    discover_official_snapshots,
    official_url,
    version_from_url,
)
from authorize_confirmatory_target import build_authorization
from confirmatory_common import PROTOCOL_ID, PROTOCOL_VERSION, iso
from prepare_confirmatory_data import validate_authorization
from score_confirmatory_cohort import adjudicate_metrics, load_bootstrap_indices
from validate_confirmatory_protocol import (
    load_and_validate,
    validate_protocol,
    validate_registry,
)


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "tools/eagc012/confirmatory_icme_protocol_v1.1.0.json"
REGISTRY_PATH = ROOT / "tools/eagc012/confirmatory_protocol_registry.json"


def freeze() -> dict[str, str]:
    return {
        "commit": "a" * 40,
        "committed_at": "2026-09-18T20:00:00Z",
        "protocol_sha256": "b" * 64,
    }


def catalog(rows: list[tuple[str, str, str]]) -> bytes:
    lines = ["icmecat_id,sc_insitu,icme_start_time,mo_end_time,Dst,SYM-H"]
    lines.extend(
        f"{identifier},Wind,{start},{end},-999,-999"
        for identifier, start, end in rows
    )
    return ("\n".join(lines) + "\n").encode()


def event_rows(start_index: int, stop_index: int) -> list[tuple[str, str, str]]:
    frozen = datetime(2026, 9, 18, 20, 0, tzinfo=timezone.utc)
    rows = []
    for index in range(start_index, stop_index):
        start = frozen + timedelta(days=index * 2)
        end = start + timedelta(hours=30)
        rows.append(
            (
                f"W{index:02d}",
                start.strftime("%Y-%m-%dT%H:%MZ"),
                end.strftime("%Y-%m-%dT%H:%MZ"),
            )
        )
    return rows


class ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
        self.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_protocol_and_frozen_artifacts_validate(self) -> None:
        load_and_validate(ROOT, verify_git=False)

    def test_protocol_version_drift_fails(self) -> None:
        changed = copy.deepcopy(self.protocol)
        changed["protocol_version"] = "1.1.1-prospective"
        with self.assertRaisesRegex(ValueError, "protocol_version"):
            validate_protocol(changed)

    def test_empty_noninferiority_contract_fails(self) -> None:
        changed = copy.deepcopy(self.protocol)
        changed["decision"]["PASS-NONINFERIOR"] = []
        with self.assertRaisesRegex(ValueError, "NI decision"):
            validate_protocol(changed)

    def test_reject_or_hold_drift_fails(self) -> None:
        for key in ("REJECT", "HOLD"):
            changed = copy.deepcopy(self.protocol)
            changed["decision"][key] = "always pass"
            with self.assertRaisesRegex(ValueError, key):
                validate_protocol(changed)

    def test_model_source_commit_drift_fails(self) -> None:
        changed = copy.deepcopy(self.protocol)
        changed["model"]["source_commit"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "model source commit"):
            validate_protocol(changed)

    def test_registry_cannot_reactivate_v1(self) -> None:
        changed = copy.deepcopy(self.registry)
        changed["versions"][0]["status"] = "READY-TO-ACCRUE"
        with self.assertRaisesRegex(ValueError, "v1 registry status"):
            validate_registry(changed)


class AccrualTests(unittest.TestCase):
    def test_discovery_orders_official_versions(self) -> None:
        html = (
            '<a href="/static/sync/icmecat/HELIO4CAST_ICMECAT_v24.csv">2.4</a>'
            '<a href="https://helioforecast.space/static/sync/icmecat/'
            'HELIO4CAST_ICMECAT_v23.csv">2.3</a>'
        )
        self.assertEqual(
            discover_official_snapshots(html),
            [("2.3", official_url("2.3")), ("2.4", official_url("2.4"))],
        )

    def test_version_url_round_trip_supports_multi_digit_minor(self) -> None:
        self.assertEqual(version_from_url(official_url("2.10")), "2.10")

    def test_source_url_version_mismatch_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly match"):
            apply_snapshot(
                None,
                raw=catalog(event_rows(1, 2)),
                source_url=official_url("2.4"),
                source_version="2.3",
                retrieved_at="2026-09-19T00:00:00Z",
                freeze=freeze(),
            )

    def test_accrual_is_append_only_across_snapshots(self) -> None:
        first = apply_snapshot(
            None,
            raw=catalog(event_rows(1, 11)),
            source_url=official_url("2.3"),
            source_version="2.3",
            retrieved_at="2026-09-19T00:00:00Z",
            freeze=freeze(),
        )
        original = copy.deepcopy(first["selected_events"])
        second = apply_snapshot(
            first,
            raw=catalog(event_rows(1, 24)),
            source_url=official_url("2.4"),
            source_version="2.4",
            retrieved_at="2026-10-01T00:00:00Z",
            freeze=freeze(),
        )
        self.assertEqual(second["state"], "MANIFEST-CANDIDATE")
        self.assertEqual(second["selected_events"][:10], original)
        self.assertEqual(second["selected_event_count"], 20)
        rendered = json.dumps(second)
        self.assertNotIn("Dst", rendered)
        self.assertNotIn("SYM-H", rendered)

    def test_catalog_revision_enters_hold(self) -> None:
        first = apply_snapshot(
            None,
            raw=catalog(event_rows(1, 3)),
            source_url=official_url("2.3"),
            source_version="2.3",
            retrieved_at="2026-09-19T00:00:00Z",
            freeze=freeze(),
        )
        revised = event_rows(1, 3)
        revised[0] = (revised[0][0], "2026-09-21T21:00Z", revised[0][2])
        second = apply_snapshot(
            first,
            raw=catalog(revised),
            source_url=official_url("2.4"),
            source_version="2.4",
            retrieved_at="2026-10-01T00:00:00Z",
            freeze=freeze(),
        )
        self.assertEqual(second["state"], "HOLD-CATALOG-REVISION")

    def test_catalog_row_deletion_enters_hold(self) -> None:
        first = apply_snapshot(
            None,
            raw=catalog(event_rows(1, 4)),
            source_url=official_url("2.3"),
            source_version="2.3",
            retrieved_at="2026-09-19T00:00:00Z",
            freeze=freeze(),
        )
        second = apply_snapshot(
            first,
            raw=catalog(event_rows(2, 4)),
            source_url=official_url("2.4"),
            source_version="2.4",
            retrieved_at="2026-10-01T00:00:00Z",
            freeze=freeze(),
        )
        self.assertEqual(second["state"], "HOLD-CATALOG-REVISION")
        self.assertIn("disappeared", second["hold_reasons"][0])

    def test_mutated_versioned_source_enters_hold(self) -> None:
        first = apply_snapshot(
            None,
            raw=catalog(event_rows(1, 3)),
            source_url=official_url("2.3"),
            source_version="2.3",
            retrieved_at="2026-09-19T00:00:00Z",
            freeze=freeze(),
        )
        second = apply_snapshot(
            first,
            raw=catalog(event_rows(1, 4)),
            source_url=official_url("2.3"),
            source_version="2.3",
            retrieved_at="2026-09-20T00:00:00Z",
            freeze=freeze(),
        )
        self.assertEqual(second["state"], "HOLD-SOURCE-MUTATION")

    def test_pre_freeze_snapshot_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "after protocol freeze"):
            apply_snapshot(
                None,
                raw=catalog(event_rows(1, 2)),
                source_url=official_url("2.3"),
                source_version="2.3",
                retrieved_at="2026-09-18T20:00:00Z",
                freeze=freeze(),
            )


class AuthorizationAndScoringTests(unittest.TestCase):
    def complete_manifest(self) -> dict:
        return apply_snapshot(
            None,
            raw=catalog(event_rows(1, 22)),
            source_url=official_url("2.3"),
            source_version="2.3",
            retrieved_at="2026-12-31T00:00:00Z",
            freeze=freeze(),
        )

    def test_authorization_requires_complete_manifest(self) -> None:
        incomplete = apply_snapshot(
            None,
            raw=catalog(event_rows(1, 3)),
            source_url=official_url("2.3"),
            source_version="2.3",
            retrieved_at="2026-09-19T00:00:00Z",
            freeze=freeze(),
        )
        with self.assertRaisesRegex(ValueError, "not complete"):
            build_authorization(
                incomplete,
                manifest_path=Path("manifest.json"),
                manifest_evidence={
                    "sha256": "c" * 64,
                    "commit": "d" * 40,
                    "committed_at": "2026-12-31T01:00:00Z",
                },
                protocol_anchor=freeze(),
            )

    def test_authorization_is_inert_until_committed(self) -> None:
        authorization = build_authorization(
            self.complete_manifest(),
            manifest_path=Path("manifest.json"),
            manifest_evidence={
                "sha256": "c" * 64,
                "commit": "d" * 40,
                "committed_at": "2026-12-31T01:00:00Z",
            },
            protocol_anchor=freeze(),
        )
        self.assertFalse(authorization["target_access_permitted"])
        validate_authorization(
            authorization,
            manifest_hash="c" * 64,
            protocol_anchor=freeze(),
            authorization_evidence={
                "sha256": "e" * 64,
                "commit": "f" * 40,
                "committed_at": iso(datetime.now(timezone.utc) - timedelta(hours=1)),
            },
        )

    def test_decision_thresholds_are_exact(self) -> None:
        self.assertEqual(
            adjudicate_metrics(
                point=-0.05,
                probability_noninferior=1.0,
                probability_superior=1.0,
                omitted=[-0.049] * 20,
            ),
            "REJECT",
        )
        self.assertEqual(
            adjudicate_metrics(
                point=0.0,
                probability_noninferior=0.90,
                probability_superior=0.89,
                omitted=[-0.01] * 20,
            ),
            "PASS-NONINFERIOR",
        )
        self.assertEqual(
            adjudicate_metrics(
                point=0.05,
                probability_noninferior=0.90,
                probability_superior=0.90,
                omitted=[0.001] * 20,
            ),
            "PASS-SUPERIOR",
        )
        self.assertEqual(
            adjudicate_metrics(
                point=0.05,
                probability_noninferior=0.90,
                probability_superior=0.90,
                omitted=[0.0] + [0.01] * 19,
            ),
            "PASS-NONINFERIOR",
        )

    def test_bootstrap_matrix_shape_and_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "indices.bin"
            path.write_bytes(bytes([0, 1, 1, 0]))
            rows = load_bootstrap_indices(path, 2, 2)
        self.assertEqual(rows, [bytes([0, 1]), bytes([1, 0])])


if __name__ == "__main__":
    unittest.main()
