"""Offline checks for curated replay, request redaction, and its spending cap."""
from __future__ import annotations

import copy
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jev_news.historical_pilot import (
    CALL_CAP, MAX_INPUT_TOKENS, PRICE_PER_MILLION, BudgetedClient,
    build_cases, case_event, direction_rule, load_corpus, model_state,
    read_key, summarize, main,
)
from jev_news.jev_analysis import STAGES, analyze
from jev_news.jev_client import MODEL, LiveJevClient
from jev_news.model import digest, stable_json


class RecordingClient:
    """A valid local response source, with no credential or network access."""

    model = MODEL

    def __init__(self):
        self.calls = 0
        self.requests = []

    def evaluate(self, state, questions):
        self.calls += 1
        self.requests.append(copy.deepcopy({"state": state, "questions": questions}))
        selected = {"relevance": "direct", "family": "financial_results",
                    "revenue": "favorable", "margin": "unknown", "discount_rate": "unknown"}
        answers = {}
        for name, question in questions.items():
            if question["type"] == "noul":
                answers[name] = {"type": "noul", "noul": 0.99 if name == "grounded_claim" else 0.01}
            elif question["type"] == "choice":
                choice = selected[name]
                probabilities = {option: 0.99 if option == choice else 0.01 / (len(question["criteria"]) - 1)
                                 for option in question["criteria"]}
                answers[name] = {"type": "choice", "choice": choice,
                                 "probabilities": probabilities, "confidence": 0.9}
            else:
                raise AssertionError("This fake never reports sufficient scale for a materiality call")
        return {"model": self.model, "answers": answers,
                "usage": {"input_tokens": 100, "output_tokens": 20}}


class HistoricalPilotTests(unittest.TestCase):
    def setUp(self):
        self.inputs, self.labels = load_corpus()
        self.cases = build_cases(self.inputs, self.labels)
        self.now = "2026-10-11T20:00:00Z"

    def state(self, case):
        event, profile = case_event(case, self.now)
        return {"company_profile": profile, "event": event, "input_cutoff": self.now,
                "prior_stage_answers": {"routing": {"test": "prior response"}}}

    def test_eleven_unique_cases_with_frozen_semantic_labels(self):
        self.assertEqual(len(self.cases), 11)
        self.assertEqual(len({c["id"] for c in self.cases}), 11)
        counts = {arm: sum(c["arm"] == arm for c in self.cases)
                  for arm in ("historical", "anonymous", "counterfactual", "control")}
        self.assertEqual(counts, {"historical": 3, "anonymous": 3, "counterfactual": 3, "control": 2})
        for case in self.cases:
            with self.subTest(case=case["id"]):
                if case["arm"] == "control":
                    self.assertIn(case["expected"]["disposition"], {"insufficient_evidence", "unrelated"})
                else:
                    expected = self.labels[case["base_id"]]["expected"]
                    direction = expected["revenue"]
                    if case["arm"] == "counterfactual":
                        direction = "adverse" if direction == "favorable" else "favorable"
                    self.assertEqual(case["expected"]["revenue"], direction)
                    self.assertTrue(case["expected"]["grounded_claim"])
                    self.assertEqual(case["expected"]["relevance"], "direct")

    def test_claims_are_exact_passages_in_curated_text_not_asserted_source_quotes(self):
        for original in self.inputs["cases"]:
            self.assertIn("not a verbatim issuer quotation", original["quote_provenance"])
        for case in self.cases:
            with self.subTest(case=case["id"]):
                if case["claim_quote"] is not None:
                    self.assertIn(case["claim_quote"], case["text"])
                case_event(case, self.now)
        broken = copy.deepcopy(self.cases[0])
        broken["claim_quote"] = "An invented passage absent from the text."
        with self.assertRaisesRegex(ValueError, "not grounded"):
            case_event(broken, self.now)

    def test_anonymous_actual_state_has_no_identifiers_dates_sources_labels_or_outcomes(self):
        original_names = ("NVIDIA", "NVDA", "Meta", "Facebook", "Instagram", "Messenger", "WhatsApp",
                          "Reels", "Apple", "AAPL", "iPhone", "Greater China", "China")
        for case in self.cases:
            with self.subTest(case=case["id"]):
                clean = model_state(self.state(case), anonymous=case["arm"] != "historical")
                encoded = json.dumps(clean)
                self.assertNotIn("http", encoded)
                self.assertNotIn(case["id"], encoded)
                for forbidden in ("event_id", "document_id", "version_id", "raw_response_path", "content_hash",
                                  "observed_at", "available_at", "source_url", "expected", "next_session",
                                  "return_pct_reported", "benchmark", "source_lineages", "base_id"):
                    self.assertNotIn('"' + forbidden + '"', encoded)
                self.assertIn("prior_stage_answers", clean)
                if case["arm"] != "historical":
                    self.assertNotIn("historical_information_cutoff", clean)
                    self.assertIsNone(re.search(r"\b(?:19|20)\d{2}\b", encoded))
                    for name in original_names:
                        self.assertNotIn(name, encoded)
                    self.assertNotIn('"FB"', encoded)

    def test_anonymous_request_and_logged_request_are_exactly_what_backend_receives(self):
        case = next(c for c in self.cases if c["id"] == "anonymous-nvda")
        event, profile = case_event(case, self.now)
        client = RecordingClient()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "run"
            report = analyze([event], profile, self.now, client, "live", directory,
                             "historical_reconstruction", state_transform=lambda s: model_state(s, anonymous=True))
            self.assertEqual(client.calls, 2)
            self.assertEqual(report["events"][0]["stages"][1]["stage"], "channels")
            files = sorted((directory / "calls").glob("*-request.json"))
            self.assertEqual(len(files), 2)
            for path, transmitted in zip(files, client.requests):
                logged = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(logged["state"], transmitted["state"])
                self.assertEqual(logged["questions"], transmitted["questions"])
                self.assertNotIn("NVIDIA", json.dumps(logged["state"]))
                self.assertNotIn("http", json.dumps(logged["state"]))
                self.assertNotIn(case["id"], json.dumps(logged["state"]))
            self.assertIn("prior_stage_answers", client.requests[1]["state"])
            evaluation = summarize(case, report, self.labels[case["base_id"]])
            self.assertIsNone(evaluation["next_session"])
            historical = copy.deepcopy(case)
            historical["arm"] = "historical"
            evaluation = summarize(historical, report, self.labels[case["base_id"]])
            self.assertEqual(evaluation["next_session"], self.labels[case["base_id"]]["next_session"])
            self.assertNotIn("next_session", json.dumps(client.requests))

    def test_budget_reserves_maximum_tokens_before_transport_and_counts_usage(self):
        first_call_ceiling = MAX_INPUT_TOKENS * PRICE_PER_MILLION / 1_000_000
        client = RecordingClient()
        budgeted = BudgetedClient(client, first_call_ceiling - 0.0000001)
        with self.assertRaisesRegex(ValueError, "no request sent"):
            budgeted.evaluate({}, {})
        self.assertEqual(client.calls, 0)
        budgeted = BudgetedClient(client, first_call_ceiling)
        budgeted.evaluate({}, {})
        self.assertEqual(client.calls, 1)
        self.assertEqual((budgeted.input_tokens, budgeted.output_tokens), (100, 20))
        with self.assertRaisesRegex(ValueError, "no request sent"):
            budgeted.evaluate({}, {})
        self.assertEqual(client.calls, 1)
        self.assertLessEqual(CALL_CAP * first_call_ceiling, 0.10)

    def test_future_profile_rejected_before_any_model_call(self):
        case = copy.deepcopy(self.cases[0])
        case["profile"]["as_of"] = "2026-10-12T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "postdate"):
            case_event(case, self.now)

    def test_continuation_reserves_prior_attempts_and_keeps_prior_token_usage(self):
        client = RecordingClient()
        # Exactly 11 maximum-size calls at $0.042/M; a chained float product
        # can represent a value below this intended dollar boundary.
        budgeted = BudgetedClient(client, 0.029568,
                                  starting_calls=10, input_tokens=1234, output_tokens=56)
        self.assertEqual(budgeted.calls, 10)
        budgeted.evaluate({}, {})
        self.assertEqual(budgeted.calls, 11)
        self.assertEqual(client.calls, 1)
        self.assertEqual((budgeted.input_tokens, budgeted.output_tokens), (1334, 76))
        with self.assertRaisesRegex(ValueError, "no request sent"):
            budgeted.evaluate({}, {})
        self.assertEqual(client.calls, 1)
        self.assertEqual(budgeted.calls, 11)

    def test_continuation_attempt_cap_does_not_reset_after_initial_twelve_attempts(self):
        transports = []

        def local_transport(body, headers, timeout):
            transports.append(body)
            return {"model": MODEL, "answers": {"q": {"type": "noul", "noul": 0.5}},
                    "usage": {"input_tokens": 100, "output_tokens": 10}}

        prior_calls = 12
        client = LiveJevClient(api_key="local-test-key-not-a-secret", max_calls=CALL_CAP - prior_calls,
                               transport=local_transport)
        budgeted = BudgetedClient(client, 0.10, starting_calls=prior_calls,
                                  input_tokens=1000, output_tokens=200)
        question = {"q": {"type": "noul", "instructions": "Is the supplied assertion supported?"}}
        for _ in range(CALL_CAP - prior_calls):
            budgeted.evaluate({}, question)
        self.assertEqual(budgeted.calls, CALL_CAP)
        self.assertEqual(len(transports), 21)
        self.assertEqual((budgeted.input_tokens, budgeted.output_tokens), (3100, 410))
        with self.assertRaisesRegex(ValueError, "call budget exhausted"):
            budgeted.evaluate({}, question)
        self.assertEqual(len(transports), 21)
        self.assertEqual(budgeted.calls, CALL_CAP)

    def test_continuation_rejects_changed_inputs_or_question_registry_before_live_key_or_transport(self):
        original_hash = digest(stable_json(self.cases))
        registry_hash = digest(stable_json(STAGES))
        for input_hash, question_hash in (("changed-input", registry_hash), (original_hash, "changed-question")):
            with self.subTest(input_hash=input_hash), tempfile.TemporaryDirectory() as temporary:
                previous = Path(temporary) / "prior"
                previous.mkdir()
                prior_summary = {"protocol": {"input_hash": input_hash, "question_registry_hash": question_hash}}
                (previous / "summary.json").write_text(json.dumps(prior_summary), encoding="utf-8")
                with patch("jev_news.historical_pilot.read_key") as key_reader, \
                        patch("jev_news.historical_pilot._http_transport") as transport:
                    with self.assertRaisesRegex(ValueError, "differ from the frozen pilot"):
                        main(["--live", "--continue-from", str(previous),
                              "--output-root", str(Path(temporary) / "output")])
                    key_reader.assert_not_called()
                    transport.assert_not_called()
                self.assertFalse((Path(temporary) / "output").exists())

    def test_outcomes_separate_from_inputs_and_cheap_baseline_has_no_outcomes(self):
        encoded = json.dumps(self.inputs)
        for field in ("next_session", "return_pct_reported", "benchmark", '"expected"'):
            self.assertNotIn(field, encoded)
        for case in self.cases:
            self.assertNotIn("next_session", case)
            self.assertNotIn("return_pct_reported", case)
            if case["arm"] == "historical":
                self.assertEqual(direction_rule(case["text"]), case["expected"]["revenue"])
                self.assertIn("next_session", self.labels[case["base_id"]])

    def test_counterfactuals_change_all_decisive_revenue_claims_coherently(self):
        counter = {c["id"]: c for c in self.cases if c["arm"] == "counterfactual"}
        nvda = counter["counterfactual-nvda"]["text"]
        self.assertIn("$5.50 billion", nvda)
        self.assertIn("decreasing demand", nvda)
        self.assertIn("cutting production", nvda)
        self.assertNotIn("$11.00 billion", nvda)
        meta = counter["counterfactual-meta"]["text"]
        self.assertIn("stronger advertiser demand", meta)
        self.assertIn("improving monetization", meta)
        self.assertNotIn("headwinds", meta)
        self.assertIn("operating margin fell", meta)  # Revenue reversal need not reverse a different channel.
        apple = counter["counterfactual-aapl"]["text"]
        self.assertIn("$94 billion", apple)
        self.assertIn("above the earlier $89-93 billion", apple)
        self.assertIn("stronger-than-expected", apple)
        self.assertIn("more upgrades", apple)
        self.assertNotIn("weaker", apple)

    def test_key_stdin_uses_pipe_without_environment_or_file_persistence(self):
        key = "local-test-key-not-a-secret"
        with patch("sys.stdin", io.StringIO(key + "\n")), patch.dict(os.environ, {}, clear=True), \
                patch("builtins.open", side_effect=AssertionError("Credential must not be written to a file")):
            self.assertEqual(read_key(from_stdin=True), key)
            self.assertNotIn("TYPESAFE_API_KEY", os.environ)
        terminal = io.StringIO(key)
        terminal.isatty = lambda: True
        with patch("sys.stdin", terminal), patch("getpass.getpass", return_value=key) as hidden:
            self.assertEqual(read_key(from_stdin=True), key)
            hidden.assert_called_once()
            self.assertEqual(terminal.tell(), 0)
        with patch("sys.stdin", io.StringIO("\n")), self.assertRaisesRegex(ValueError, "No key received"):
            read_key(from_stdin=True)


if __name__ == "__main__":
    unittest.main()
