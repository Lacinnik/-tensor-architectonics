from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from adjudicate import adjudicate, percentile, validate_policy


POLICY_PATH = Path(__file__).resolve().parent / "claim_policy.json"
FROZEN_V05 = (
    Path(__file__).resolve().parent
    / "frozen"
    / "v0.5-validation-predictions.json"
)


def metrics(candidate_offset: float, baseline_offset: float) -> dict:
    rows = []
    for index in range(20):
        observed = -float(20 + index * 4)
        rows.append(
            {
                "event_id": f"E{index:02d}",
                "observed_SYM_H_min": observed,
                "EAGC_prediction": observed + candidate_offset,
                "Newell_prediction": observed + baseline_offset,
                "V_Bs_prediction": observed + baseline_offset * 1.1,
                "I_Q_prediction": observed + baseline_offset * 1.2,
                "Burton_OBrien_McPherron_prediction": (
                    observed + baseline_offset * 1.3
                ),
            }
        )
    return {"decision": "REJECT", "validation_predictions": rows}


class ClaimAdjudicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.policy["bootstrap_replicates"] = 1000

    def test_clear_superiority_passes(self) -> None:
        result = adjudicate(
            metrics(candidate_offset=1.0, baseline_offset=10.0),
            self.policy,
            scope="in-domain",
        )
        self.assertEqual(result["decision"], "PASS-SUPERIOR")
        self.assertTrue(result["noninferiority_gate_pass"])
        self.assertTrue(result["superiority_gate_pass"])
        self.assertEqual(result["legacy_gate_decision"], "REJECT")

    def test_practical_equivalence_is_not_mislabeled_superiority(self) -> None:
        result = adjudicate(
            metrics(candidate_offset=10.2, baseline_offset=10.0),
            self.policy,
            scope="in-domain",
        )
        self.assertEqual(result["decision"], "PASS-NONINFERIOR")
        self.assertTrue(result["noninferiority_gate_pass"])
        self.assertFalse(result["superiority_gate_pass"])

    def test_material_inferiority_rejects(self) -> None:
        result = adjudicate(
            metrics(candidate_offset=12.0, baseline_offset=10.0),
            self.policy,
            scope="in-domain",
        )
        self.assertEqual(result["decision"], "REJECT")
        self.assertFalse(result["noninferiority_gate_pass"])

    def test_transport_scope_is_explicit(self) -> None:
        result = adjudicate(
            metrics(candidate_offset=12.0, baseline_offset=10.0),
            self.policy,
            scope="transport",
        )
        self.assertEqual(result["decision"], "TRANSPORT-REJECT")

    def test_secondary_baseline_cannot_veto_primary_claim(self) -> None:
        evidence = metrics(candidate_offset=1.0, baseline_offset=10.0)
        for row in evidence["validation_predictions"]:
            row["V_Bs_prediction"] = row["observed_SYM_H_min"]
        result = adjudicate(evidence, self.policy, scope="in-domain")
        self.assertEqual(result["decision"], "PASS-SUPERIOR")
        self.assertLess(
            result["secondary_comparisons"]["V_Bs"]["rmse_improvement"], 0
        )

    def test_policy_rejects_unregistered_scope_or_bad_probability(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported scope"):
            adjudicate(metrics(1.0, 10.0), self.policy, scope="other")
        broken = copy.deepcopy(self.policy)
        broken["minimum_noninferiority_probability"] = 1.5
        with self.assertRaisesRegex(
            ValueError, "minimum_noninferiority_probability"
        ):
            validate_policy(broken)

    def test_percentile_interpolates(self) -> None:
        self.assertEqual(percentile([0.0, 10.0], 0.25), 2.5)

    def test_frozen_v05_snapshot_yields_noninferiority_pass(self) -> None:
        frozen = json.loads(FROZEN_V05.read_text(encoding="utf-8"))
        result = adjudicate(frozen, self.policy, scope="in-domain")
        self.assertEqual(result["decision"], "PASS-NONINFERIOR")
        self.assertAlmostEqual(
            result["primary_comparison"]["rmse_improvement"],
            0.04151041821054808,
        )
        self.assertAlmostEqual(
            result["primary_comparison"][
                "minimum_leave_one_event_out_improvement"
            ],
            -0.007138743610292235,
        )


if __name__ == "__main__":
    unittest.main()
