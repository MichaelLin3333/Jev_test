"""Focused checks for leakage, window isolation, scoring and feature mapping."""
import copy
import unittest
from .core import ROOT, OLD, LABELS, read, metrics, rank, safe_state, average, digest
from .questions import definitions, feature_vector, FEATURE_COUNT, ordered_probabilities
from .data_sets import old_windows, verify_dataset
from .search import fit, model_predictions, load_market_model


class SearchTests(unittest.TestCase):
    def test_frozen_sources_and_evaluator(self):
        verify_dataset()

    def test_exactly_ten_question_graphs(self):
        for number in range(1, 11):
            self.assertTrue(definitions(number))
        for number in (0, 11):
            with self.assertRaises(ValueError):
                definitions(number)

    def test_cdf_mapping_and_declared_projection(self):
        values, conflict = ordered_probabilities(0.25, 0.55)
        self.assertFalse(conflict)
        self.assertAlmostEqual(values["flat"], 0.30)
        values, conflict = ordered_probabilities(0.8, 0.2)
        self.assertTrue(conflict)
        self.assertEqual(values, {"up": 0.5, "flat": 0.0, "down": 0.5})

    def test_feature_definitions_and_missing_channel(self):
        questions = definitions(6)["features"]
        answers = {}
        for name, question in questions.items():
            if question["type"] == "noul":
                answers[name] = {"noul": 0.4}
            else:
                count = len(question["criteria"])
                answers[name] = {"probabilities": {key: 1/count for key in question["criteria"]}}
        vector = feature_vector(answers)
        self.assertEqual(len(vector), FEATURE_COUNT)
        self.assertEqual(vector[-1], 0.0)
        self.assertAlmostEqual(vector[7], 0.0)
        del answers["priced_reaction_known"]
        self.assertEqual(feature_vector(answers)[6], 0.0)

    def test_no_outcomes_pass_through_input_allowlist(self):
        case = copy.deepcopy(read(ROOT / "data" / "development_cases.json")[0])
        case.update(label="down", actual="down", future_return=-0.9, exit_close=1, outcomes={"label": "down"})
        state = safe_state(case, [0.0]*10, {"up": 0.4, "flat": 0.2, "down": 0.4})
        for forbidden in ("label", "actual", "future_return", "exit_close", "outcomes"):
            self.assertNotIn(forbidden, state)
        self.assertEqual(state["pre_cutoff_market"]["relative_return_20"], 0.0)

    def test_missing_prediction_is_wrong_and_max_brier(self):
        result = metrics(["a", "b"], {"a": {"up": 1., "flat": 0., "down": 0.}}, {"a": {"label": "up"}, "b": {"label": "up"}})
        self.assertEqual(result["full_coverage_accuracy"], 0.5)
        self.assertEqual(result["forecast_coverage"], 0.5)
        self.assertEqual(result["selection_brier_failure_penalized"], 1.0)
        self.assertFalse(result["goal_70_reached"])

    def test_accuracy_ranking_precedes_brier(self):
        self.assertGreater(rank({"full_coverage_accuracy": .6, "balanced_accuracy": .3, "selection_brier_failure_penalized": 1.}), rank({"full_coverage_accuracy": .5, "balanced_accuracy": .9, "selection_brier_failure_penalized": .1}))
        self.assertIsNone(average([{"up": 1., "flat": 0., "down": 0.}, None]))

    def test_no_same_stock_window_overlap_for_any_holdout_source(self):
        blocked = old_windows()
        cases = read(ROOT / "data" / "holdout_cases.json")
        urls = set()
        texts = set()
        for case in cases:
            ticker = case["company"]["ticker"]
            sessions = set(case["window"]["sessions"])
            for prior in blocked.get(ticker, []):
                self.assertFalse(sessions.intersection(prior["sessions"]), (case["case_id"], prior["id"]))
            blocked.setdefault(ticker, []).append({"id": case["case_id"], "sessions": list(sessions)})
            source = case["articles"][0]
            self.assertNotIn(source["url"], urls)
            urls.add(source["url"])
            text_hash = digest(source["text"])
            self.assertNotIn(text_hash, texts)
            texts.add(text_hash)
        self.assertEqual(len(cases), 30)

    def test_train_only_statistical_fit_and_exact_development_copies(self):
        cases = read(ROOT / "data" / "development_cases.json")
        outcomes = read(ROOT / "data" / "development_outcomes.json")
        market = read(ROOT / "data" / "development_market.json")
        self.assertEqual(outcomes, read(OLD / "data" / "development_outcomes.json"))
        self.assertEqual(market, read(OLD / "data" / "development_market_features.json"))
        model, ids = fit(cases, outcomes, market, None, "tree")
        expected = {case["case_id"] for case in cases if case["split"] == "train" and outcomes[case["case_id"]]["label"] in LABELS}
        self.assertEqual(set(ids), expected)
        self.assertEqual(len(ids), 74)
        self.assertEqual(len(model_predictions(load_market_model(), cases, market)), 120)


if __name__ == "__main__":
    unittest.main()
