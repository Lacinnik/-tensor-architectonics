from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_gate import Row, decision_for, feature_vector, quality_result


def row(minute: int, *, missing_speed: bool = False, suffix_scale: float = 1.0) -> Row:
    return Row(
        t=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minute),
        bmag=8.0 * suffix_scale,
        bz=-6.0 * suffix_scale,
        speed=None if missing_speed else 450.0 * suffix_scale,
        density=5.0,
        pressure=2.0 * suffix_scale,
        ae=200.0,
        al=-150.0,
        symh=-10.0 * suffix_scale,
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
        decision, _ = decision_for(summaries, self.policy)
        self.assertEqual(decision, "HOLD-DATA")

    def test_four_scorable_events_cannot_pass(self) -> None:
        summaries = [
            {"event_id": name, "quality_status": "SCORABLE", "SYM_H_min": -10}
            for name in ("A", "B", "C", "D")
        ]
        decision, _ = decision_for(summaries, self.policy)
        self.assertEqual(decision, "HOLD-SAMPLE")

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
        status, coverages, gaps, failures = quality_result(
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
