from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_gate import (
    POLICY_PATH,
    Row,
    burton_obrien_mcpherron,
    clean,
    decision_for,
    evaluate_gate,
    feature_vector,
    load_events,
    load_policy,
    newell_coupling,
    paired_bootstrap_probability,
    quality_result,
)


def row(
    minute: int,
    *,
    missing_speed: bool = False,
    missing_symh: bool = False,
    suffix_scale: float = 1.0,
    by_value: float = 0.0,
    bz_value: float = -6.0,
) -> Row:
    return Row(
        t=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minute),
        bmag=8.0 * suffix_scale,
        by=by_value * suffix_scale,
        bz=bz_value * suffix_scale,
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
            "minimum_development_events": 20,
            "minimum_rmse_improvement": 0.05,
            "minimum_bootstrap_probability": 0.9,
            "bootstrap_replicates": 1000,
            "bootstrap_seed": 12012,
            "required_baselines": [
                "V_Bs",
                "I_Q",
                "Newell",
                "Burton_OBrien_McPherron",
            ],
            "eagc_model": {
                "kind": "standardized_ridge",
                "features": [
                    "south_hours",
                    "SYM_H_prefix_min",
                    "SYM_H_recent",
                    "pressure_peak",
                ],
                "alpha": 0.1,
            },
        }

    def test_non_scorable_event_forces_hold_data(self) -> None:
        summaries = [
            {
                "event_id": "A",
                "cohort": "development",
                "quality_status": "SCORABLE",
                "SYM_H_min": -10,
            },
            {
                "event_id": "B",
                "cohort": "development",
                "quality_status": "HOLD-DATA",
                "SYM_H_min": -20,
            },
            {
                "event_id": "C",
                "cohort": "validation",
                "quality_status": "SCORABLE",
                "SYM_H_min": -30,
            },
            {
                "event_id": "D",
                "cohort": "validation",
                "quality_status": "SCORABLE",
                "SYM_H_min": -40,
            },
        ]
        decision, blockers = decision_for(summaries, self.policy)
        self.assertEqual(decision, "HOLD-DATA")
        self.assertTrue(
            any(
                "development sample 2 is below preregistered minimum 20"
                in item
                for item in blockers
            )
        )

    def test_four_scorable_events_cannot_pass(self) -> None:
        summaries = [
            {
                "event_id": name,
                "cohort": "development",
                "quality_status": "SCORABLE",
                "SYM_H_min": -10,
                "I_Q": 1.0,
                "V_Bs": 1.0,
                "Newell": 1.0,
                "Burton_OBrien_McPherron": 1.0,
                "EAGC": 1.0,
                "south_hours": 1.0,
                "SYM_H_prefix_min": 1.0,
                "SYM_H_recent": 1.0,
                "pressure_peak": 1.0,
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
            "development_events": [
                {
                    "event_id": "A",
                    "sheet_tab": "A",
                    "months": ["202601", "202603"],
                    "start": "2026-01-31T00:00:00Z",
                    "cutoff": "2026-02-01T00:00:00Z",
                    "end": "2026-03-02T00:00:00Z",
                }
            ],
            "validation_events": [],
        }
        with self.assertRaisesRegex(ValueError, "every month crossed"):
            load_events(policy)

        policy["development_events"][0]["months"] = [
            "202603",
            "202602",
            "202601",
        ]
        with self.assertRaisesRegex(ValueError, "chronological order"):
            load_events(policy)

    def test_event_cutoff_must_match_frozen_rule(self) -> None:
        policy = {
            "forecast_cutoff_rule": {"prefix_minutes": 720},
            "development_events": [
                {
                    "event_id": "A",
                    "sheet_tab": "A",
                    "months": ["202601"],
                    "start": "2026-01-01T00:00:00Z",
                    "cutoff": "2026-01-01T13:00:00Z",
                    "end": "2026-01-02T00:00:00Z",
                }
            ],
            "validation_events": [],
        }
        with self.assertRaisesRegex(ValueError, "forecast cutoff rule"):
            load_events(policy)

    def test_event_times_must_be_utc_and_minute_aligned(self) -> None:
        policy = {
            "forecast_cutoff_rule": {"prefix_minutes": 720},
            "development_events": [
                {
                    "event_id": "A",
                    "sheet_tab": "A",
                    "months": ["202601"],
                    "start": "2026-01-01T00:00:00+03:00",
                    "cutoff": "2026-01-01T12:00:00+03:00",
                    "end": "2026-01-02T00:00:00+03:00",
                }
            ],
            "validation_events": [],
        }
        with self.assertRaisesRegex(ValueError, "must use UTC"):
            load_events(policy)

        policy["development_events"][0].update(
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
            "development_events": [
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
            "validation_events": [],
        }
        with self.assertRaisesRegex(ValueError, "event_id values must be unique"):
            load_events(policy)

        policy["development_events"][1]["event_id"] = "B"
        with self.assertRaisesRegex(ValueError, "event windows overlap"):
            load_events(policy)

    def test_artifact_identifiers_cannot_escape_output_directories(self) -> None:
        policy = {
            "forecast_cutoff_rule": {"prefix_minutes": 720},
            "development_events": [
                {
                    "event_id": "../gate_metrics",
                    "sheet_tab": "A",
                    "months": ["202601"],
                    "start": "2026-01-01T00:00:00Z",
                    "cutoff": "2026-01-01T12:00:00Z",
                    "end": "2026-01-02T00:00:00Z",
                }
            ],
            "validation_events": [],
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

            policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
            policy["minimum_rmse_improvement"] = 0
            path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "minimum_rmse_improvement"):
                load_policy(path)

            policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
            policy["bootstrap_replicates"] = 100
            path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bootstrap_replicates"):
                load_policy(path)

    def test_newell_control_matches_published_coupling_function(self) -> None:
        rows = [row(minute, by_value=0.0, bz_value=-6.0) for minute in range(10)]
        expected = 450.0 ** (4 / 3) * 6.0 ** (2 / 3)
        self.assertAlmostEqual(newell_coupling(rows), expected)

    def test_burton_obrien_control_responds_to_southward_field(self) -> None:
        northward = [
            row(minute, bz_value=6.0) for minute in range(120)
        ]
        southward = [
            row(minute, bz_value=-12.0) for minute in range(120)
        ]
        quiet = burton_obrien_mcpherron(northward)
        driven = burton_obrien_mcpherron(southward)
        self.assertIsNotNone(quiet)
        self.assertIsNotNone(driven)
        assert quiet is not None
        assert driven is not None
        self.assertGreater(driven, quiet)

    def test_paired_bootstrap_is_deterministic(self) -> None:
        actual = [-10.0, -20.0, -30.0, -40.0]
        candidate = actual.copy()
        baseline = [-5.0, -10.0, -15.0, -20.0]
        first = paired_bootstrap_probability(
            actual,
            candidate,
            baseline,
            replicates=1000,
            seed=42,
        )
        second = paired_bootstrap_probability(
            actual,
            candidate,
            baseline,
            replicates=1000,
            seed=42,
        )
        self.assertEqual(first, second)
        self.assertEqual(first, 1.0)

    def test_complete_acceptance_gates_can_produce_pass(self) -> None:
        summaries = []
        for cohort_index, cohort in enumerate(("development", "validation")):
            for index in range(1, 21):
                signal = float(index + cohort_index)
                target = -(10.0 + 3.0 * signal)
                summaries.append(
                    {
                        "event_id": f"{cohort[0].upper()}{index:02d}",
                        "cohort": cohort,
                        "quality_status": "SCORABLE",
                        "SYM_H_min": target,
                        "I_Q": 1.0,
                        "V_Bs": 1.0,
                        "Newell": 1.0,
                        "Burton_OBrien_McPherron": 1.0,
                        "south_hours": signal,
                        "SYM_H_prefix_min": signal,
                        "SYM_H_recent": signal,
                        "pressure_peak": signal,
                    }
                )
        decision, blockers, metrics = evaluate_gate(summaries, self.policy)
        self.assertEqual(decision, "PASS")
        self.assertEqual(blockers, [])
        self.assertEqual(set(metrics["comparisons"]), set(self.policy["required_baselines"]))
        self.assertTrue(
            all(
                comparison["rmse_gate_pass"]
                and comparison["bootstrap_gate_pass"]
                and comparison["single_event_gate_pass"]
                for comparison in metrics["comparisons"].values()
            )
        )

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
