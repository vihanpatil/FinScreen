"""
test_compute_agreement.py — unit tests for compute_agreement.py, over
SYNTHETIC data only. Never reads data/labels.parquet, spotcheck/sample_400
.parquet/.json, or any real owner review export.

Run: python3 -m pytest spotcheck/test_compute_agreement.py -v
 or: python3 spotcheck/test_compute_agreement.py
"""

import math
import unittest

from compute_agreement import (
    wilson_ci,
    summarize,
    agreement_rate_with_ci,
    assert_distress_excluded_from_headline,
    HEADLINE_FIELDS,
)


class TestWilsonCI(unittest.TestCase):
    def test_hand_computed_10_of_10(self):
        # 10/10 successes — Wilson CI should have a lower bound well below
        # 100% (unlike a naive Wald interval which would give [100%,100%]).
        est, lo, hi = wilson_ci(10, 10)
        self.assertAlmostEqual(est, 1.0)
        # Hand-computed Wilson 95% CI lower bound for 10/10 is ~0.7225 (via
        # the closed-form formula with z=1.959963984540054).
        self.assertAlmostEqual(lo, 0.7225, places=3)
        self.assertAlmostEqual(hi, 1.0, places=3)

    def test_hand_computed_50_of_100(self):
        # Textbook example: 50/100, Wilson 95% CI ≈ [0.4038, 0.5962].
        est, lo, hi = wilson_ci(50, 100)
        self.assertAlmostEqual(est, 0.5)
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)

    def test_hand_computed_0_of_20(self):
        # 0/20 successes — lower bound must be exactly 0, upper bound > 0
        # (Wilson doesn't collapse to a degenerate [0,0] interval).
        est, lo, hi = wilson_ci(0, 20)
        self.assertAlmostEqual(est, 0.0)
        self.assertEqual(lo, 0.0)
        self.assertGreater(hi, 0.0)
        # Hand-computed Wilson upper bound for 0/20 ≈ 0.1611
        self.assertAlmostEqual(hi, 0.1611, places=3)

    def test_n_zero_returns_none(self):
        est, lo, hi = wilson_ci(0, 0)
        self.assertIsNone(est)
        self.assertIsNone(lo)
        self.assertIsNone(hi)

    def test_wilson_differs_from_naive_wald_near_boundary(self):
        # At small n near a boundary proportion, Wilson and Wald must
        # differ meaningfully — this guards against an accidental Wald
        # (normal-approximation) implementation being swapped in.
        est, lo, hi = wilson_ci(9, 10)
        wald_lo = est - 1.96 * math.sqrt(est * (1 - est) / 10)
        self.assertNotAlmostEqual(lo, wald_lo, places=2)


class TestSummarizeAndAgreement(unittest.TestCase):
    def test_basic_counts(self):
        rows = [
            {"field": "sentiment", "judgment": "agree"},
            {"field": "sentiment", "judgment": "agree"},
            {"field": "sentiment", "judgment": "disagree"},
            {"field": "sentiment", "judgment": "unsure"},
            {"field": "sentiment", "judgment": ""},  # unfilled
        ]
        summary = summarize(rows)
        self.assertEqual(summary["agree"], 2)
        self.assertEqual(summary["disagree"], 1)
        self.assertEqual(summary["unsure"], 1)
        self.assertEqual(summary["unfilled"], 1)
        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["judged"], 4)
        self.assertAlmostEqual(summary["coverage"], 4 / 5)

    def test_agreement_rate_excludes_unsure_and_unfilled(self):
        rows = [
            {"field": "sentiment", "judgment": "agree"},
            {"field": "sentiment", "judgment": "agree"},
            {"field": "sentiment", "judgment": "agree"},
            {"field": "sentiment", "judgment": "disagree"},
            {"field": "sentiment", "judgment": "unsure"},
            {"field": "sentiment", "judgment": ""},
        ]
        summary = summarize(rows)
        est, lo, hi = agreement_rate_with_ci(summary)
        # 3 agree / (3 agree + 1 disagree) = 0.75, n=4 for the CI, NOT n=6.
        self.assertAlmostEqual(est, 0.75)
        expected_est, expected_lo, expected_hi = wilson_ci(3, 4)
        self.assertAlmostEqual(lo, expected_lo)
        self.assertAlmostEqual(hi, expected_hi)

    def test_missing_data_path_all_unfilled(self):
        rows = [
            {"field": "sentiment", "judgment": ""},
            {"field": "sentiment", "judgment": ""},
        ]
        summary = summarize(rows)
        self.assertEqual(summary["judged"], 0)
        est, lo, hi = agreement_rate_with_ci(summary)
        self.assertIsNone(est)
        self.assertEqual(summary["unfilled"], 2)
        self.assertEqual(summary["coverage"], 0.0)

    def test_missing_data_never_imputed(self):
        # An unfilled judgment must never silently count as "agree" or
        # "disagree" — verify counts stay exactly as input, not rounded
        # toward either bucket.
        rows = [{"field": "sentiment", "judgment": ""} for _ in range(50)]
        rows += [{"field": "sentiment", "judgment": "agree"}]
        summary = summarize(rows)
        self.assertEqual(summary["agree"], 1)
        self.assertEqual(summary["disagree"], 0)
        self.assertEqual(summary["unfilled"], 50)


class TestTierAndCategoryBreakdown(unittest.TestCase):
    def test_per_tier_breakdown(self):
        rows = [
            {"field": "sentiment", "judgment": "agree", "primary_tier": "A"},
            {"field": "sentiment", "judgment": "disagree", "primary_tier": "A"},
            {"field": "sentiment", "judgment": "agree", "primary_tier": "B"},
            {"field": "sentiment", "judgment": "agree", "primary_tier": "C"},
            {"field": "sentiment", "judgment": "agree", "primary_tier": "C"},
        ]
        tier_a = [r for r in rows if r["primary_tier"] == "A"]
        tier_b = [r for r in rows if r["primary_tier"] == "B"]
        tier_c = [r for r in rows if r["primary_tier"] == "C"]
        self.assertEqual(summarize(tier_a)["agree"], 1)
        self.assertEqual(summarize(tier_a)["disagree"], 1)
        self.assertEqual(summarize(tier_b)["agree"], 1)
        self.assertEqual(summarize(tier_c)["agree"], 2)

    def test_per_section_type_breakdown(self):
        rows = [
            {"field": "sentiment", "judgment": "agree", "section_type": "MDA"},
            {"field": "sentiment", "judgment": "disagree", "section_type": "MDA"},
            {"field": "sentiment", "judgment": "agree", "section_type": "EX99_PRESS_RELEASE"},
        ]
        mda = [r for r in rows if r["section_type"] == "MDA"]
        pr = [r for r in rows if r["section_type"] == "EX99_PRESS_RELEASE"]
        s_mda = summarize(mda)
        s_pr = summarize(pr)
        self.assertEqual(s_mda["agree"], 1)
        self.assertEqual(s_mda["disagree"], 1)
        self.assertEqual(s_pr["agree"], 1)
        self.assertEqual(s_pr["disagree"], 0)

    def test_category_isolation(self):
        # sentiment judgments must not leak into guidance_direction's bucket.
        rows = [
            {"field": "sentiment", "judgment": "agree"},
            {"field": "guidance_direction", "judgment": "disagree"},
        ]
        sentiment_rows = [r for r in rows if r["field"] == "sentiment"]
        guidance_rows = [r for r in rows if r["field"] == "guidance_direction"]
        self.assertEqual(summarize(sentiment_rows)["agree"], 1)
        self.assertEqual(summarize(sentiment_rows)["disagree"], 0)
        self.assertEqual(summarize(guidance_rows)["agree"], 0)
        self.assertEqual(summarize(guidance_rows)["disagree"], 1)


class TestDistressExclusion(unittest.TestCase):
    def test_distress_tier_excluded_from_headline_fields_constant(self):
        self.assertNotIn("distress_tier", HEADLINE_FIELDS)
        self.assertIn("sentiment", HEADLINE_FIELDS)
        self.assertIn("guidance_direction", HEADLINE_FIELDS)
        self.assertIn("red_flags", HEADLINE_FIELDS)

    def test_assert_distress_excluded_raises_on_leak(self):
        leaked_rows = [
            {"field": "sentiment", "judgment": "agree"},
            {"field": "distress_tier", "judgment": "agree"},  # should never be here
        ]
        with self.assertRaises(AssertionError):
            assert_distress_excluded_from_headline(leaked_rows)

    def test_assert_distress_excluded_passes_when_clean(self):
        clean_rows = [
            {"field": "sentiment", "judgment": "agree"},
            {"field": "red_flags", "judgment": "disagree"},
        ]
        # should not raise
        assert_distress_excluded_from_headline(clean_rows)


if __name__ == "__main__":
    unittest.main(verbosity=2)
