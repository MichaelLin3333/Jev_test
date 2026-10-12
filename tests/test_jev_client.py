from __future__ import annotations

import io
import json
import os
import unittest
import urllib.error
from unittest.mock import Mock, patch

from jev_news.jev_client import (
    ENDPOINT, MODEL, JevClientError, LiveJevClient, _NoRedirects,
    _http_transport, validate_response,
)


def questions():
    return {
        "relevant": {"type": "noul", "instructions": "Is this relevant?"},
        "family": {"type": "choice", "instructions": "Which family?",
                   "criteria": {"earnings": "Earnings", "other": "Other"}},
        "materiality": {"type": "score", "instructions": "How material?",
                        "criteria": ["None", "Limited", "Material"]},
    }


def response():
    """Hand-authored API-shape fixture; not an actual Jev evaluation."""
    return {
        "model": MODEL,
        "answers": {
            "relevant": {"type": "noul", "noul": 0.95},
            "family": {"type": "choice", "choice": "earnings",
                       "probabilities": {"earnings": 0.9, "other": 0.1},
                       "confidence": 0.7},
            "materiality": {"type": "score", "score": 1.8,
                            "legend": {"0": "None", "1": "Limited", "2": "Material"},
                            "probabilities": {"0": 0.05, "1": 0.1, "2": 0.85},
                            "confidence": 0.6},
        },
        "usage": {"input_tokens": 100, "output_tokens": 20, "extra": "preserve"},
        "request_id": "fixture-request",
    }


class JevResponseTests(unittest.TestCase):
    def test_valid_response_preserves_extra_fields_and_identity(self):
        result = response()
        self.assertIs(validate_response(result, questions()), result)
        self.assertEqual(result["usage"]["extra"], "preserve")
        self.assertEqual(result["request_id"], "fixture-request")

    def test_exact_answer_ids_types_and_model_are_required(self):
        for mutation in (
            lambda item: item["answers"].pop("relevant"),
            lambda item: item["answers"].update(extra={"type": "noul", "noul": 1.0}),
            lambda item: item["answers"]["relevant"].update(type="choice"),
            lambda item: item.update(model="jev-latest"),
            lambda item: item.update(model="different-model"),
        ):
            with self.subTest(mutation=mutation):
                item = response()
                mutation(item)
                with self.assertRaises(ValueError):
                    validate_response(item, questions())

    def test_invalid_numbers_cannot_masquerade_as_probabilities(self):
        for value in (True, "0.8", float("nan"), float("inf"), -0.01, 1.01, 10 ** 1000):
            with self.subTest(value=repr(value)[:50]):
                item = response()
                item["answers"]["relevant"]["noul"] = value
                with self.assertRaises(ValueError):
                    validate_response(item, questions())

    def test_probability_options_sum_confidence_and_argmax_are_checked(self):
        invalid_answers = [
            {"probabilities": {"earnings": 0.8}},
            {"probabilities": {"earnings": 0.8, "other": 0.1}},
            {"probabilities": {"earnings": 1.1, "other": -0.1}},
            {"probabilities": {"earnings": float("nan"), "other": 0.1}},
            {"choice": "unknown"},
            {"choice": "other"},
            {"confidence": True},
            {"confidence": float("inf")},
        ]
        for invalid in invalid_answers:
            with self.subTest(invalid=invalid):
                item = response()
                item["answers"]["family"].update(invalid)
                with self.assertRaises(ValueError):
                    validate_response(item, questions())

    def test_equal_argmax_and_tiny_sum_rounding_are_allowed(self):
        item = response()
        item["answers"]["family"].update(
            choice="other", probabilities={"earnings": 0.5, "other": 0.5})
        validate_response(item, questions())
        item["answers"]["family"].update(
            choice="earnings", probabilities={"earnings": 0.9000001, "other": 0.1})
        validate_response(item, questions())

    def test_score_is_zero_based_and_legend_and_weighted_mean_match(self):
        for mutation in (
            lambda answer: answer.update(score=0.8),
            lambda answer: answer.update(score=3.0),
            lambda answer: answer.update(legend={"1": "None", "2": "Limited", "3": "Material"}),
            lambda answer: answer["legend"].update({"0": "Different rubric"}),
            lambda answer: answer.update(probabilities={"1": 0.05, "2": 0.1, "3": 0.85}),
        ):
            with self.subTest(mutation=mutation):
                item = response()
                mutation(item["answers"]["materiality"])
                with self.assertRaises(ValueError):
                    validate_response(item, questions())

    def test_usage_is_required_and_integer_valued(self):
        for invalid in (None, {}, {"input_tokens": True, "output_tokens": 3},
                        {"input_tokens": 3, "output_tokens": -1}):
            with self.subTest(invalid=invalid):
                item = response()
                item["usage"] = invalid
                with self.assertRaises(ValueError):
                    validate_response(item, questions())


class JevClientTests(unittest.TestCase):
    def test_missing_key_fails_without_transport(self):
        transport = Mock()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "TYPESAFE_API_KEY"):
                LiveJevClient(transport=transport)
        transport.assert_not_called()

    def test_environment_key_request_contract_and_budget(self):
        fixture = response()
        transport = Mock(return_value=fixture)
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-secret"}):
            client = LiveJevClient(timeout=12.5, max_calls=1, transport=transport)
        state = {"evidence": "Synthetic earnings announcement"}
        question_map = questions()
        self.assertIs(client.evaluate(state, question_map), fixture)
        transport.assert_called_once_with(
            {"model": MODEL, "state": state, "questions": question_map},
            {"Authorization": "Bearer test-secret", "Content-Type": "application/json",
             "Accept": "application/json"}, 12.5)
        self.assertEqual(client.calls, 1)
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            client.evaluate(state, question_map)
        self.assertEqual(transport.call_count, 1)

    def test_failed_transport_attempt_is_counted_and_never_retried(self):
        transport = Mock(side_effect=urllib.error.URLError("secret body test-secret"))
        client = LiveJevClient(api_key="test-secret", max_calls=1, transport=transport)
        with self.assertRaises(JevClientError) as caught:
            client.evaluate({}, questions())
        self.assertNotIn("test-secret", str(caught.exception))
        self.assertNotIn("secret body", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)
        self.assertEqual(client.calls, 1)
        transport.assert_called_once()
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            client.evaluate({}, questions())

    def test_http_error_is_sanitized_and_response_body_is_closed(self):
        body = io.BytesIO(b"secret-body test-secret")
        error = urllib.error.HTTPError(ENDPOINT, 429, "test-secret", {}, body)
        client = LiveJevClient(api_key="test-secret", transport=Mock(side_effect=error))
        with self.assertRaisesRegex(JevClientError, "HTTP 429") as caught:
            client.evaluate({}, questions())
        self.assertNotIn("test-secret", str(caught.exception))
        self.assertTrue(body.closed)
        self.assertEqual(client.calls, 1)

    def test_bad_response_is_not_hidden_and_consumes_attempt(self):
        invalid = response()
        invalid["answers"]["relevant"]["noul"] = 8
        transport = Mock(return_value=invalid)
        client = LiveJevClient(api_key="test-key", transport=transport)
        with self.assertRaisesRegex(ValueError, "valid range"):
            client.evaluate({}, questions())
        self.assertEqual(client.calls, 1)
        transport.assert_called_once()

    def test_invalid_request_configuration_never_spends_a_call(self):
        for settings in ({"model": "jev-latest"}, {"timeout": 0}, {"timeout": float("nan")},
                         {"timeout": True}, {"max_calls": True}, {"max_calls": 0},
                         {"api_key": "test\r\nsecret"}):
            with self.subTest(settings=settings):
                arguments = {"api_key": "test-key", **settings}
                with self.assertRaises(ValueError):
                    LiveJevClient(**arguments)
        transport = Mock()
        client = LiveJevClient(api_key="test-key", transport=transport)
        for state, question_map in (([], questions()), ({"value": float("nan")}, questions()),
                                    ({}, {}), ({}, {"bad": {"type": "choice", "instructions": "?"}})):
            with self.subTest(state=state, question_map=question_map):
                with self.assertRaises(ValueError):
                    client.evaluate(state, question_map)
        self.assertEqual(client.calls, 0)
        transport.assert_not_called()

    def test_default_transport_posts_utf8_json_to_fixed_endpoint(self):
        fixture = response()
        context = Mock()
        context.__enter__ = Mock(return_value=io.StringIO(json.dumps(fixture)))
        context.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = context
        headers = {"Authorization": "Bearer test-key", "Content-Type": "application/json"}
        with patch("jev_news.jev_client.urllib.request.build_opener", return_value=opener) as build:
            result = _http_transport({"state": {"text": "Synthetic café"}}, headers, 3.5)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, ENDPOINT)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), {"state": {"text": "Synthetic café"}})
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 3.5)
        self.assertIsInstance(build.call_args.args[0], _NoRedirects)
        self.assertEqual(result, fixture)

    def test_redirect_handler_never_forwards_credentials(self):
        handler = _NoRedirects()
        with self.assertRaises(JevClientError):
            handler.redirect_request(None, None, 302, "Found", {}, "https://untrusted.example")


if __name__ == "__main__":
    unittest.main()
