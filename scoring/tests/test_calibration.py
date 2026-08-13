"""Offline tests for scoring/calibration.py -- pure functions, no database
or network needed. Ported from the original JS test suite (25 tests, all
passing) with identical expected behavior.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calibration import (
    calibration_score,
    classify_financial,
    classify_overall,
    classify_reception,
    compute_calibration,
    score_to_grade,
    tally_votes,
)


class TestClassifyFinancial(unittest.TestCase):
    def test_hit_when_gross_is_at_least_2x_budget(self):
        result = classify_financial(100, {"boxOfficeWorldwide": 250})
        self.assertEqual(result["label"], "hit")
        self.assertEqual(result["multiple"], 2.5)

    def test_flop_when_gross_is_below_budget(self):
        result = classify_financial(100, {"boxOfficeWorldwide": 60})
        self.assertEqual(result["label"], "flop")

    def test_mixed_when_gross_covers_budget_but_not_2x(self):
        result = classify_financial(100, {"boxOfficeWorldwide": 150})
        self.assertEqual(result["label"], "mixed")

    def test_falls_back_to_domestic_gross_when_worldwide_missing(self):
        result = classify_financial(100, {"boxOfficeDomestic": 300})
        self.assertEqual(result["label"], "hit")

    def test_unknown_when_budget_or_gross_missing(self):
        self.assertEqual(classify_financial(None, {"boxOfficeWorldwide": 300})["label"], "unknown")
        self.assertEqual(classify_financial(100, {})["label"], "unknown")


class TestClassifyReception(unittest.TestCase):
    def test_strong_when_average_at_least_70(self):
        result = classify_reception({"audienceScore": 80, "criticScore": 90})
        self.assertEqual(result["label"], "strong")
        self.assertEqual(result["average"], 85)

    def test_weak_when_average_below_40(self):
        result = classify_reception({"audienceScore": 20, "criticScore": 30})
        self.assertEqual(result["label"], "weak")

    def test_mixed_in_between(self):
        result = classify_reception({"audienceScore": 55})
        self.assertEqual(result["label"], "mixed")

    def test_unknown_when_no_scores_present(self):
        self.assertEqual(classify_reception({})["label"], "unknown")


class TestClassifyOverall(unittest.TestCase):
    def test_financial_hit_or_flop_wins_outright(self):
        self.assertEqual(classify_overall({"label": "hit"}, {"label": "weak"}), "hit")
        self.assertEqual(classify_overall({"label": "flop"}, {"label": "strong"}), "flop")

    def test_financial_mixed_broken_by_reception(self):
        self.assertEqual(classify_overall({"label": "mixed"}, {"label": "strong"}), "hit")
        self.assertEqual(classify_overall({"label": "mixed"}, {"label": "weak"}), "flop")
        self.assertEqual(classify_overall({"label": "mixed"}, {"label": "mixed"}), "mixed")

    def test_falls_back_to_reception_alone_when_financial_unknown(self):
        self.assertEqual(classify_overall({"label": "unknown"}, {"label": "strong"}), "hit")
        self.assertEqual(classify_overall({"label": "unknown"}, {"label": "unknown"}), "unknown")


class TestTallyVotes(unittest.TestCase):
    def test_counts_and_picks_a_majority(self):
        votes = [
            {"role": "creative", "vote": "greenlight"},
            {"role": "finance", "vote": "pass"},
            {"role": "marketing", "vote": "greenlight"},
            {"role": "distribution", "vote": "greenlight"},
        ]
        tally = tally_votes(votes)
        self.assertEqual(tally["greenlight"], 3)
        self.assertEqual(tally["pass"], 1)
        self.assertEqual(tally["majority"], "greenlight")

    def test_split_on_a_tie(self):
        votes = [
            {"role": "creative", "vote": "greenlight"},
            {"role": "finance", "vote": "pass"},
        ]
        self.assertEqual(tally_votes(votes)["majority"], "split")


class TestCalibrationScore(unittest.TestCase):
    def test_matched_vote_scores_100(self):
        self.assertEqual(calibration_score("greenlight", "hit"), 100)
        self.assertEqual(calibration_score("pass", "flop"), 100)

    def test_mismatched_vote_scores_0(self):
        self.assertEqual(calibration_score("greenlight", "flop"), 0)
        self.assertEqual(calibration_score("pass", "hit"), 0)

    def test_mixed_reality_gives_partial_credit_regardless_of_vote(self):
        self.assertEqual(calibration_score("greenlight", "mixed"), 65)
        self.assertEqual(calibration_score("pass", "mixed"), 65)

    def test_split_vote_scores_below_neutral(self):
        self.assertEqual(calibration_score("split", "hit"), 45)

    def test_unknown_outcome_is_neutral(self):
        self.assertEqual(calibration_score("greenlight", "unknown"), 50)


class TestScoreToGrade(unittest.TestCase):
    def test_boundaries_map_to_the_right_letter(self):
        self.assertEqual(score_to_grade(100), "A")
        self.assertEqual(score_to_grade(90), "A")
        self.assertEqual(score_to_grade(89), "B")
        self.assertEqual(score_to_grade(60), "C")
        self.assertEqual(score_to_grade(40), "D")
        self.assertEqual(score_to_grade(39), "F")


class TestComputeCalibration(unittest.TestCase):
    VOTES = [
        {"role": "creative", "argument": "Strong director, original premise.", "vote": "greenlight"},
        {"role": "finance", "argument": "Budget is reasonable against comps.", "vote": "greenlight"},
        {"role": "marketing", "argument": "Great trailer-ability.", "vote": "greenlight"},
        {"role": "distribution", "argument": "Clear release window.", "vote": "greenlight"},
    ]

    def test_unanimous_greenlight_on_an_actual_hit_scores_perfectly(self):
        actual = {
            "boxOfficeDomestic": 300_000_000,
            "boxOfficeWorldwide": 711_800_000,
            "imdbRating": 8.1,
            "audienceScore": 78,
            "criticScore": 88,
        }
        computed = compute_calibration(self.VOTES, actual, budget=190_000_000)
        self.assertEqual(computed["financial"]["label"], "hit")
        self.assertEqual(computed["reception"]["label"], "strong")
        self.assertEqual(computed["overall"], "hit")
        self.assertEqual(computed["tally"]["majority"], "greenlight")
        self.assertEqual(computed["score"], 100)
        self.assertEqual(computed["grade"], "A")

    def test_unanimous_greenlight_on_an_actual_flop_scores_zero(self):
        actual = {
            "boxOfficeDomestic": 20_000_000,
            "boxOfficeWorldwide": 40_000_000,
            "imdbRating": 4.0,
            "audienceScore": 30,
            "criticScore": 25,
        }
        computed = compute_calibration(self.VOTES, actual, budget=190_000_000)
        self.assertEqual(computed["overall"], "flop")
        self.assertEqual(computed["score"], 0)
        self.assertEqual(computed["grade"], "F")

    def test_missing_budget_falls_back_to_reception_alone(self):
        actual = {"audienceScore": 80, "criticScore": 90}
        computed = compute_calibration(self.VOTES, actual, budget=None)
        self.assertEqual(computed["financial"]["label"], "unknown")
        self.assertEqual(computed["overall"], "hit")


if __name__ == "__main__":
    unittest.main()
