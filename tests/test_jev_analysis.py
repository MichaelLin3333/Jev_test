from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from jev_news.jev_analysis import (
    FixtureJevClient,
    analyze,
    comparison,
    load_fixture,
    prepare_events,
    seed_fixture,
)
from jev_news.model import stamp, parse_time
from jev_news.store import Archive


EARLY = "2026-10-10T12:20:00Z"
LATE = "2026-10-10T12:40:00Z"
FUTURE = "2026-10-10T13:00:00Z"


class JevAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = load_fixture()
        self.profile = copy.deepcopy(self.fixture["profile"])
        self.archive_directory = self.root / "archive"
        seed_fixture(self.archive_directory, self.fixture)
        self.archive = Archive(self.archive_directory, "synthetic")
        self.run_number = 0

    def tearDown(self):
        self.archive.close()
        self.temp.cleanup()

    def documents(self, cutoff=LATE):
        return list(self.archive.snapshot(stamp(parse_time(cutoff))))

    def events(self, cutoff=LATE, documents=None, profile=None):
        return prepare_events(
            self.documents(cutoff) if documents is None else documents,
            self.profile if profile is None else profile,
            cutoff,
            "synthetic",
        )

    def run_analysis(self, cutoff=LATE, events=None, backend=None):
        self.run_number += 1
        directory = self.root / f"run-{self.run_number}"
        backend = backend or FixtureJevClient(self.fixture)
        report = analyze(
            self.events(cutoff) if events is None else events,
            self.profile,
            cutoff,
            backend,
            "fixture",
            directory,
            "synthetic",
        )
        return report, directory, backend

    @staticmethod
    def event_named(events, event_id):
        return next(event for event in events if event["event_id"] == event_id)

    def test_archive_cutoff_selects_correction_without_future_leakage(self):
        earlier = self.event_named(self.events(EARLY), "customer-capex")
        later = self.event_named(self.events(LATE), "customer-capex")
        self.assertEqual(earlier["revision"], 1)
        self.assertEqual(later["revision"], 2)
        self.assertEqual(earlier["comparison"]["current"], 24)
        self.assertEqual(later["comparison"]["current"], 21)
        self.assertAlmostEqual(earlier["comparison"]["relative_change"], 0.20)
        self.assertAlmostEqual(later["comparison"]["relative_change"], 0.05)
        self.assertFalse(earlier["superseded_evidence"])
        self.assertEqual(len(later["superseded_evidence"]), 2)
        early_text = json.dumps(earlier)
        self.assertNotIn("corrected", early_text)
        self.assertNotIn("USD 21 billion", early_text)
        self.assertEqual(later["comparison"]["market_consensus"], "not_supplied")
        self.assertEqual(later["comparison"]["stock_return_implication"], "not_estimated")

    def test_duplicate_copy_adds_provenance_without_extra_event_or_weight(self):
        documents = self.documents(EARLY)
        without_copy = [document for document in documents if document["provider_key"] != "capex-copy"]
        full_events = self.events(EARLY, documents)
        reduced_events = self.events(EARLY, without_copy)
        full = self.event_named(full_events, "customer-capex")
        reduced = self.event_named(reduced_events, "customer-capex")
        self.assertEqual((len(full["evidence"]), len(reduced["evidence"])), (2, 1))
        self.assertEqual(full["source_lineages"], ["cloudharbor-announcement"])
        self.assertEqual(full["comparison"], reduced["comparison"])
        full_report, _, full_backend = self.run_analysis(EARLY, full_events)
        reduced_report, _, reduced_backend = self.run_analysis(EARLY, reduced_events)
        self.assertEqual(full_report["combined"], reduced_report["combined"])
        self.assertEqual(full_backend.calls, reduced_backend.calls)
        self.assertEqual(full_report["combined"]["favorable_events"].count("customer-capex"), 1)

    def test_all_observation_clocks_are_enforced_before_model_calls(self):
        for clock in ("first_seen_at", "version_first_observed_at", "snapshot_observed_at"):
            with self.subTest(clock=clock):
                documents = self.documents(EARLY)
                documents[0][clock] = FUTURE
                backend = FixtureJevClient(self.fixture)
                with self.assertRaisesRegex(ValueError, "cutoff|clock"):
                    events = self.events(EARLY, documents)
                    self.run_analysis(EARLY, events, backend)
                self.assertEqual(backend.calls, 0)

    def test_future_company_profile_is_rejected_before_calls(self):
        profile = copy.deepcopy(self.profile)
        profile["available_at"] = FUTURE
        backend = FixtureJevClient(self.fixture)
        with self.assertRaisesRegex(ValueError, "profile.*cutoff"):
            events = self.events(EARLY, profile=profile)
            self.run_analysis(EARLY, events, backend)
        self.assertEqual(backend.calls, 0)

    def test_future_profile_passage_is_rejected_even_for_synthetic_inputs(self):
        profile = copy.deepcopy(self.profile)
        profile["evidence"][0]["available_at"] = FUTURE
        with self.assertRaisesRegex(ValueError, "exposure.*cutoff|evidence.*cutoff"):
            self.events(EARLY, profile=profile)

    def test_future_baseline_is_rejected_before_calls(self):
        documents = self.documents(EARLY)
        original = next(document for document in documents if document["provider_key"] == "capex-original")
        original["metadata"]["baseline"]["available_at"] = FUTURE
        backend = FixtureJevClient(self.fixture)
        with self.assertRaisesRegex(ValueError, "Baseline.*cutoff"):
            events = self.events(EARLY, documents)
            self.run_analysis(EARLY, events, backend)
        self.assertEqual(backend.calls, 0)

    def test_claim_quote_must_be_exact_not_a_model_invention(self):
        documents = self.documents(EARLY)
        original = next(document for document in documents if document["provider_key"] == "capex-original")
        original["metadata"]["claim_quote"] = "NVIDIA revenue will grow 20 percent"
        with self.assertRaisesRegex(ValueError, "Claim quote"):
            self.events(EARLY, documents)

    def test_numerical_comparison_requires_grounded_ordered_amounts(self):
        original = next(document for document in self.fixture["documents"] if document["id"] == "capex-original")
        for field, value in (("current", 25), ("prior", 24), ("current", True), ("prior", float("nan"))):
            with self.subTest(field=field, value=value):
                baseline = copy.deepcopy(original["baseline"])
                baseline[field] = value
                with self.assertRaises(ValueError):
                    comparison(baseline, original["text"], EARLY)
        baseline = copy.deepcopy(original["baseline"])
        baseline["quote"] = "USD 24 billion, versus USD 20 billion"
        with self.assertRaisesRegex(ValueError, "exact passage"):
            comparison(baseline, original["text"], EARLY)
        baseline = copy.deepcopy(original["baseline"])
        baseline["period"] = "FY2028"
        with self.assertRaisesRegex(ValueError, "period"):
            comparison(baseline, original["text"], EARLY)

    def test_missing_expectation_is_unknown_and_never_zero_surprise(self):
        event = self.event_named(self.events(), "export-policy")
        self.assertEqual(event["comparison"], {"status": "unknown", "market_consensus": "not_supplied"})

    def test_metadata_and_vague_headline_stop_with_unknown_direction(self):
        report, _, _ = self.run_analysis()
        for event_id in ("filing", "vague-capacity"):
            with self.subTest(event_id=event_id):
                event = self.event_named(report["events"], event_id)
                self.assertEqual(event["disposition"], "insufficient_evidence")
                self.assertEqual(event["economic_direction"], "unknown")
                self.assertIsNone(event["materiality"])
                self.assertEqual([stage["stage"] for stage in event["stages"]], ["routing"])

    def test_rumor_is_kept_separate_from_combined_supported_channels(self):
        report, _, _ = self.run_analysis()
        rumor = self.event_named(report["events"], "packaging-rumor")
        self.assertEqual(rumor["disposition"], "unverified_rumor")
        self.assertEqual(rumor["economic_direction"], "adverse")
        self.assertEqual(report["combined"]["rumor_events"], ["packaging-rumor"])
        self.assertNotIn("packaging-rumor", report["combined"]["adverse_events"])
        self.assertEqual(report["combined"]["favorable_events"], ["customer-capex"])
        self.assertEqual(report["combined"]["adverse_events"], ["export-policy"])
        self.assertEqual(report["combined"]["economic_balance"], "mixed_channels")

    def test_materiality_requires_company_exposure_and_stages_receive_prior_answers(self):
        report, directory, _ = self.run_analysis()
        customer = self.event_named(report["events"], "customer-capex")
        policy = self.event_named(report["events"], "export-policy")
        self.assertIsNone(customer["materiality"])
        self.assertIsNotNone(policy["materiality"])
        self.assertEqual([stage["stage"] for stage in policy["stages"]], ["routing", "channels", "materiality"])
        for event in report["events"]:
            for stage in event["stages"]:
                request = json.loads((directory / stage["request_path"]).read_text(encoding="utf-8"))
                if stage["stage"] == "routing":
                    self.assertNotIn("prior_stage_answers", request["state"])
                else:
                    prior = request["state"]["prior_stage_answers"]
                    self.assertEqual(prior["routing"], event["stages"][0]["answers"])
                    if stage["stage"] == "materiality":
                        self.assertEqual(prior["channels"], event["stages"][1]["answers"])
                self.assertEqual(request["state"]["event"]["claim_quote"], event["claim_quote"])

    def test_run_directory_is_append_only_and_cannot_overwrite_a_previous_report(self):
        report, directory, backend = self.run_analysis()
        saved = (directory / "report.json").read_bytes()
        calls = backend.calls
        with self.assertRaises(FileExistsError):
            analyze(self.events(), self.profile, LATE, backend, "fixture", directory, "synthetic")
        self.assertEqual((directory / "report.json").read_bytes(), saved)
        self.assertEqual(backend.calls, calls)
        self.assertEqual(json.loads(saved)["input_hash"], report["input_hash"])

    def test_scripted_distributions_are_explicit_and_no_return_forecast_is_created(self):
        report, _, _ = self.run_analysis()
        self.assertEqual(report["backend"], "fixture")
        self.assertTrue(report["synthetic_inputs"])
        self.assertIsNone(report["return_probabilities"])
        self.assertIsNone(report["price_target"])
        self.assertEqual(report["forecast_status"], "not_estimated")
        for event in report["events"]:
            for stage in event["stages"]:
                self.assertEqual(stage["model"], "scripted-fixture-not-a-model")

    def test_backend_failure_leaves_failed_report_with_no_silent_fallback(self):
        class FailingBackend:
            model = "failing-test-backend"
            calls = 0

            def evaluate(self, state, questions):
                self.calls += 1
                raise ValueError("Simulated invalid provider response")

        backend = FailingBackend()
        directory = self.root / "failed-run"
        with self.assertRaisesRegex(ValueError, "Simulated"):
            analyze(self.events(), self.profile, LATE, backend, "live", directory, "synthetic")
        report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["events"], [])
        self.assertEqual(report["evaluation_calls"], 1)
        errors = list((directory / "calls").glob("*-error.json"))
        self.assertEqual(len(errors), 1)
        self.assertEqual(json.loads(errors[0].read_text())["status"], "failed_no_fallback")

    def test_engine_validates_backend_responses_before_using_them(self):
        class InvalidBackend(FixtureJevClient):
            def evaluate(self, state, questions):
                response = super().evaluate(state, questions)
                response["answers"]["grounded_claim"]["noul"] = float("nan")
                return response

        backend = InvalidBackend(self.fixture)
        directory = self.root / "invalid-run"
        with self.assertRaises(ValueError):
            analyze(self.events(), self.profile, LATE, backend, "fixture", directory, "synthetic")
        report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["events"], [])


if __name__ == "__main__":
    unittest.main()
