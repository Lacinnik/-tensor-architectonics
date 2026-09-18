import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from accrue_confirmatory_cohort import build_manifest
from validate_confirmatory_protocol import load_protocol, validate_protocol


PROTOCOL_PATH = Path(__file__).with_name("confirmatory_icme_protocol.json")


class ConfirmatoryProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))

    def test_frozen_protocol_is_ready_to_accrue(self) -> None:
        validate_protocol(self.protocol)

    def test_target_access_before_manifest_freeze_fails(self) -> None:
        changed = copy.deepcopy(self.protocol)
        changed["sources"]["predictors_and_target"]["access_boundary"] = "Query OMNI immediately."
        with self.assertRaisesRegex(ValueError, "target access guard"):
            validate_protocol(changed)

    def test_event_replacement_fails(self) -> None:
        changed = copy.deepcopy(self.protocol)
        changed["cohort"]["replacement_policy"] = "REPLACE_FAILED"
        with self.assertRaisesRegex(ValueError, "replacement"):
            validate_protocol(changed)

    def test_sir_transfer_fails(self) -> None:
        changed = copy.deepcopy(self.protocol)
        changed["claim_scope"]["transport_exclusions"] = []
        with self.assertRaisesRegex(ValueError, "SIR"):
            validate_protocol(changed)

    def test_superiority_margin_relaxation_fails(self) -> None:
        changed = copy.deepcopy(self.protocol)
        changed["comparison"]["superiority_margin_relative_rmse"] = 0.0
        with self.assertRaisesRegex(ValueError, "superiority margin"):
            validate_protocol(changed)

    def test_model_or_feature_drift_fails(self) -> None:
        changed = copy.deepcopy(self.protocol)
        changed["model"]["features"].append("target_leak")
        with self.assertRaisesRegex(ValueError, "feature set"):
            validate_protocol(changed)

    def test_protocol_file_loader_rejects_unfrozen_state(self) -> None:
        changed = copy.deepcopy(self.protocol)
        changed["status"] = "DRAFT"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "protocol.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "frozen pre-target"):
                load_protocol(path)

    def test_manifest_builder_is_target_blind_and_deterministic(self) -> None:
        frozen = datetime(2026, 9, 18, 20, 0, tzinfo=timezone.utc)
        rows = ["icmecat_id,sc_insitu,icme_start_time,mo_end_time,Dst,SYM-H"]
        for index in range(21, 0, -1):
            start = frozen + timedelta(days=index * 2)
            end = start + timedelta(hours=30)
            rows.append(
                f"W{index:02d},Wind,{start:%Y-%m-%dT%H:%MZ},{end:%Y-%m-%dT%H:%MZ},-999,-999"
            )
        rows.append("S01,STEREO-A,2026-12-01T00:00Z,2026-12-02T06:00Z,-999,-999")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.csv"
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            manifest = build_manifest(
                path,
                source_url="https://helioforecast.space/static/sync/icmecat/HELIO4CAST_ICMECAT_v24.csv",
                source_version="2.4",
                retrieved_at="2026-12-31T00:00:00Z",
                freeze_commit="a" * 40,
                freeze_committed_at="2026-09-18T20:00:00Z",
            )
        self.assertEqual(manifest["state"], "FROZEN-CANDIDATE")
        self.assertFalse(manifest["target_access_permitted"])
        self.assertEqual(manifest["selected_event_count"], 20)
        self.assertEqual(manifest["selected_events"][0]["icmecat_id"], "W01")
        self.assertNotIn("Dst", json.dumps(manifest))
        self.assertNotIn("SYM-H", json.dumps(manifest))

    def test_manifest_builder_requires_post_freeze_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.csv"
            path.write_text(
                "icmecat_id,sc_insitu,icme_start_time,mo_end_time\n"
                "W01,Wind,2026-09-20T00:00Z,2026-09-21T06:00Z\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "strictly after"):
                build_manifest(
                    path,
                    source_url="https://helioforecast.space/static/sync/icmecat/HELIO4CAST_ICMECAT_v24.csv",
                    source_version="2.4",
                    retrieved_at="2026-09-18T20:00:00Z",
                    freeze_commit="a" * 40,
                    freeze_committed_at="2026-09-18T20:00:00Z",
                )


if __name__ == "__main__":
    unittest.main()
