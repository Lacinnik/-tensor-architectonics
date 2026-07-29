from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_gate import (
    POLICY_PATH,
    Row,
    clean,
    decision_for,
    feature_vector,
    load_events,
    load_policy,
    quality_result,
)


def row(
    minute: int,
    *,
    missing_speed: bool = False,
    missing_symh: bool = False,
    suffix_scale: float = 1.0,
) -> Row:
    return Row(
        t=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minute),
        bmag=8.0 * suffix_scale,
        bz=-6.0 * suffix_scale,
        speed=None if missing_speed else 450.0 * suffix_scale,
        density=5.0,
        pressure=2.0 * suffix_scale,
        ae=200.0,
        al=-150.0,
        symh=None if missing_symh else -10.0 * suffix_scale,
    )


class GateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = {
            "minimum_independent_events": 20,
            "required_baselines": [
                "V_Bs",
                "I_Q",
                "Newell",
                "Burton_OBrien_McPherron",
            ],
        }

    def test_non_scorable_event_forces_hold_data(self) -> None:
        summaries = [
            {"event_id": "A", "quality_status": "SCORABLE", "SYM_H_min": -10},
            {"event_id": "B", "quality_status": "HOLD-DATA", "SYM_H_min": -20},
            {"event_id": "C", "quality_status": "SCORABLE", "SYM_H_min": -30},
            {"event_id": "D", "quality_status": "SCORABLE", "SYM_H_min": -40},
        ]
        decision, blockers = decision_for(summaries, self.policy)
        self.assertEqual(decision, "HOLD-DATA")
        self.assertTrue(
            any("sample 4 is below preregistered minimum 20" in item for item in blockers)
        )
        self.assertTrue(
            any("required control baselines not implemented" in item for item in blockers)
        )

    def test_four_scorable_events_cannot_pass(self) -> None:
        summaries = [
            {
                "event_id": name,
                "quality_status": "SCORABLE",
                "SYM_H_min": -10,
                "I_Q": 1.0,
                "V_Bs": 1.0,
                "EAGC": 1.0,
            }
            for name in ("A", "B", "C", "D")
        ]
        decision, _ = decision_for(summaries, self.policy)
        self.assertEqual(decision, "HOLD-SAMPLE")

    def test_missing_prefix_features_fail_closed(self) -> None:
        rows = [row(minute) for minute in range(60)]
        status, _, _, _, _, failures = quality_result(
            rows,
            required_fields=["bz", "speed", "density", "pressure"],
            gap_fields=["bz", "speed", "pressure"],
            minimum_coverage=0.9,
            maximum_gap=15,
            monotonic=True,
            duplicates=0,
            prefix_invariant=True,
            prefix_features_available=False,
        )
        self.assertEqual(status, "HOLD-DATA")
        self.assertIn("HOLD-DATA", failures)

    def test_target_quality_fails_closed(self) -> None:
        feature_rows = [row(minute) for minute in range(60)]
        target_rows = [
            row(minute, missing_symh=70 <= minute < 90)
            for minute in range(60, 120)
        ]
        status, _, _, target_coverages, target_gaps, failures = quality_result(
            feature_rows,
            target_rows=target_rows,
            required_fields=["bz", "speed", "density", "pressure"],
            gap_fields=["bz", "speed", "pressure"],
            minimum_coverage=0.9,
            maximum_gap=15,
            monotonic=True,
            duplicates=0,
            prefix_invariant=True,
        )
        self.assertEqual(status, "HOLD-DATA")
        self.assertLess(target_coverages["symh"], 0.9)
        self.assertEqual(target_gaps["symh"], 20)
        self.assertIn("HOLD-GAP", failures)

    def test_future_predictor_gaps_do_not_change_feature_quality(self) -> None:
        feature_rows = [row(minute) for minute in range(60)]
        target_rows = [
            row(minute, missing_speed=True) for minute in range(60, 120)
        ]
        status, coverages, gaps, target_coverages, _, failures = quality_result(
            feature_rows,
            target_rows=target_rows,
            required_fields=["bz", "speed", "density", "pressure"],
            gap_fields=["bz", "speed", "pressure"],
            minimum_coverage=0.9,
            maximum_gap=15,
            monotonic=True,
            duplicates=0,
            prefix_invariant=True,
        )
        self.assertEqual(status, "SCORABLE")
        self.assertEqual(coverages["speed"], 1.0)
        self.assertEqual(gaps["speed"], 0)
        self.assertEqual(target_coverages["symh"], 1.0)
        self.assertEqual(failures, [])

    def test_event_window_requires_every_crossed_month(self) -> None:
        policy = {
            "forecast_cutoff_rule": {"prefix_minutes": 1440},
            "events": [
                {
                    "event_id": "A",
                    "sheet_tab": "A",
                    "months": ["202601", "202603"],
                    "start": "2026-01-31T00:00:00Z",
                    "cutoff": "2026-02-01T00:00:00Z",
                    "end": "2026-03-02T00:00:00Z",
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "every month crossed"):
            load_events(policy)

        policy["events"][0]["months"] = ["202603", "202602", "202601"]
        with self.assertRaisesRegex(ValueError, "chronological order"):
            load_events(policy)

    def test_event_cutoff_must_match_frozen_rule(self) -> None:
        policy = {
            "forecast_cutoff_rule": {"prefix_minutes": 720},
            "events": [
                {
                    "event_id": "A",
                    "sheet_tab": "A",
                    "months": ["202601"],
                    "start": "2026-01-01T00:00:00Z",
                    "cutoff": "2026-01-01T13:00:00Z",
                    "end": "2026-01-02T00:00:00Z",
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "forecast cutoff rule"):
            load_events(policy)

    def test_event_times_must_be_utc_and_minute_aligned(self) -> None:
        policy = {
            "forecast_cutoff_rule": {"prefix_minutes": 720},
            "events": [
                {
                    "event_id": "A",
                    "sheet_tab": "A",
                    "months": ["202601"],
                    "start": "2026-01-01T00:00:00+03:00",
                    "cutoff": "2026-01-01T12:00:00+03:00",
                    "end": "2026-01-02T00:00:00+03:00",
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "must use UTC"):
            load_events(policy)

        policy["events"][0].update(
            {
                "start": "2026-01-01T00:00:30Z",
                "cutoff": "2026-01-01T12:00:30Z",
                "end": "2026-01-02T00:00:30Z",
            }
        )
        with self.assertRaisesRegex(ValueError, "whole minute"):
            load_events(policy)

    def test_registered_events_must_be_unique_and_independent(self) -> None:
        policy = {
            "forecast_cutoff_rule": {"prefix_minutes": 720},
            "events": [
                {
                    "event_id": "A",
                    "sheet_tab": "A",
                    "months": ["202601"],
                    "start": "2026-01-01T00:00:00Z",
                    "cutoff": "2026-01-01T12:00:00Z",
                    "end": "2026-01-03T00:00:00Z",
                },
                {
                    "event_id": "A",
                    "sheet_tab": "B",
                    "months": ["202601"],
                    "start": "2026-01-02T00:00:00Z",
                    "cutoff": "2026-01-02T12:00:00Z",
                    "end": "2026-01-04T00:00:00Z",
                },
            ],
        }
        with self.assertRaisesRegex(ValueError, "event_id values must be unique"):
            load_events(policy)

        policy["events"][1]["event_id"] = "B"
        with self.assertRaisesRegex(ValueError, "event windows overlap"):
            load_events(policy)

    def test_artifact_identifiers_cannot_escape_output_directories(self) -> None:
        policy = {
            "forecast_cutoff_rule": {"prefix_minutes": 720},
            "events": [
                {
                    "event_id": "../gate_metrics",
                    "sheet_tab": "A",
                    "months": ["202601"],
                    "start": "2026-01-01T00:00:00Z",
                    "cutoff": "2026-01-01T12:00:00Z",
                    "end": "2026-01-02T00:00:00Z",
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "invalid event_id"):
            load_events(policy)

    def test_official_magnetic_fill_values_are_removed(self) -> None:
        self.assertIsNone(clean("bmag", "9999.99"))
        self.assertIsNone(clean("bz", "9999.99"))
        self.assertEqual(clean("bz", "1200.0"), 1200.0)

    def test_policy_thresholds_and_fields_are_validated(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "policy.json"

            policy["minimum_coverage"] = -1
            path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "minimum_coverage"):
                load_policy(path)

            policy["minimum_coverage"] = 0.9
            policy["gap_fields"] = ["not_a_row_field"]
            path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "gap_fields"):
                load_policy(path)

    def test_suffix_cannot_change_feature_vector(self) -> None:
        cutoff = datetime(2026, 1, 1, 0, 30, tzinfo=timezone.utc)
        prefix = [row(minute) for minute in range(30)]
        ordinary_suffix = [row(minute) for minute in range(30, 60)]
        changed_suffix = [
            row(minute, suffix_scale=10.0) for minute in range(30, 60)
        ]
        self.assertEqual(
            feature_vector(prefix + ordinary_suffix, cutoff),
            feature_vector(prefix + changed_suffix, cutoff),
        )

    def test_gap_and_coverage_fail_closed(self) -> None:
        rows = [row(minute, missing_speed=10 <= minute < 30) for minute in range(60)]
        status, coverages, gaps, _, _, failures = quality_result(
            rows,
            required_fields=["bz", "speed", "density", "pressure"],
            gap_fields=["bz", "speed", "pressure"],
            minimum_coverage=0.9,
            maximum_gap=15,
            monotonic=True,
            duplicates=0,
            prefix_invariant=True,
        )
        self.assertEqual(status, "HOLD-DATA")
        self.assertLess(coverages["speed"], 0.9)
        self.assertEqual(gaps["speed"], 20)
        self.assertIn("HOLD-GAP", failures)


if __name__ == "__main__":
    unittest.main()
