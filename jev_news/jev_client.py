"""Small, explicitly live client for the official Jev HTTP API.

Contract: https://docs.typesafe.ai/api
Version pin and limits: https://docs.typesafe.ai/models
Questions in one request read the same state independently. The caller owns
sequential orchestration and archiving; this module never writes credentials.
There are deliberately no automatic retries: a timeout can follow a billed call.
"""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from typing import Callable

MODEL = "jev-1.13.0"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
PROBABILITY_TOLERANCE = 1e-6
Transport = Callable[[dict, dict, float], dict]


class JevClientError(RuntimeError):
    """A sanitized transport failure; response bodies and credentials are omitted."""


def _number(value: object, field: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid Jev response: {field} must be a number.")
    try:
        numeric = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"Invalid Jev response: {field} must be finite.") from None
    if not math.isfinite(numeric) or not low <= numeric <= high:
        raise ValueError(f"Invalid Jev response: {field} is outside its valid range.")
    return numeric


def _description(value: object) -> bool:
    return isinstance(value, (str, dict, list)) and bool(value)


def _validate_questions(questions: dict) -> None:
    if not isinstance(questions, dict) or not questions:
        raise ValueError("Jev questions must be a nonempty dictionary.")
    for question_id, question in questions.items():
        if not isinstance(question_id, str) or not question_id:
            raise ValueError("Jev question IDs must be nonempty strings.")
        if not isinstance(question, dict) or not _description(question.get("instructions")):
            raise ValueError("Every Jev question needs instructions.")
        question_type = question.get("type")
        criteria = question.get("criteria")
        if question_type == "choice":
            if not isinstance(criteria, dict) or not 1 <= len(criteria) <= 255:
                raise ValueError("Jev Choice requires 1 to 255 options.")
            if any(not isinstance(key, str) or not key for key in criteria):
                raise ValueError("Jev Choice options must be nonempty strings.")
            if any(value is not None and not _description(value) for value in criteria.values()):
                raise ValueError("Invalid Jev Choice option description.")
        elif question_type == "score":
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10:
                raise ValueError("Jev Score requires 2 to 10 ordered levels.")
            if any(not _description(value) for value in criteria):
                raise ValueError("Invalid Jev Score level description.")
        elif question_type == "noul":
            if criteria is not None and (
                not isinstance(criteria, dict)
                or not set(criteria).issubset({"true", "false"})
                or any(not _description(value) for value in criteria.values())
            ):
                raise ValueError("Invalid Jev Noul criteria.")
        else:
            raise ValueError("Unsupported Jev question type.")


def _distribution(value: object, expected_keys: set[str]) -> dict[str, float]:
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ValueError("Invalid Jev response: probability options do not match the question.")
    probabilities = {
        key: _number(number, "probability", 0.0, 1.0)
        for key, number in value.items()
    }
    if not math.isclose(math.fsum(probabilities.values()), 1.0,
                        rel_tol=0.0, abs_tol=PROBABILITY_TOLERANCE):
        raise ValueError("Invalid Jev response: probabilities must sum to one.")
    return probabilities


def validate_response(response: dict, questions: dict) -> dict:
    """Validate the pinned API response, preserving all fields and the same object.

    Choice/Noul/Score shapes follow https://docs.typesafe.ai/api. Probability
    sums allow 1e-6 rounding error. Score uses zero-based rubric indices, not
    percentages or return magnitudes. Unknown response fields are retained.
    """
    _validate_questions(questions)
    if not isinstance(response, dict) or response.get("model") != MODEL:
        raise ValueError("Invalid Jev response: the returned model does not match the version pin.")
    answers = response.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise ValueError("Invalid Jev response: answer IDs do not match the questions.")
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("Invalid Jev response: usage is missing.")
    for field in ("input_tokens", "output_tokens"):
        value = usage.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("Invalid Jev response: token usage must be nonnegative integers.")
    for question_id, question in questions.items():
        answer = answers[question_id]
        question_type = question["type"]
        if not isinstance(answer, dict) or answer.get("type") != question_type:
            raise ValueError("Invalid Jev response: answer type does not match its question.")
        if question_type == "noul":
            _number(answer.get("noul"), "noul", 0.0, 1.0)
            continue
        _number(answer.get("confidence"), "confidence", 0.0, 1.0)
        if question_type == "choice":
            probabilities = _distribution(answer.get("probabilities"), set(question["criteria"]))
            choice = answer.get("choice")
            if not isinstance(choice, str) or choice not in probabilities:
                raise ValueError("Invalid Jev response: unknown Choice selection.")
            if probabilities[choice] < max(probabilities.values()):
                raise ValueError("Invalid Jev response: Choice selection is not a highest-probability option.")
        else:
            criteria = question["criteria"]
            expected_keys = {str(index) for index in range(len(criteria))}
            probabilities = _distribution(answer.get("probabilities"), expected_keys)
            legend = answer.get("legend")
            if not isinstance(legend, dict) or set(legend) != expected_keys:
                raise ValueError("Invalid Jev response: Score legend indices do not match its levels.")
            if any(not isinstance(value, str) or not value for value in legend.values()):
                raise ValueError("Invalid Jev response: Score legend descriptions must be strings.")
            for index, description in enumerate(criteria):
                if isinstance(description, str) and legend[str(index)] != description:
                    raise ValueError("Invalid Jev response: Score legend does not match its rubric.")
            score = _number(answer.get("score"), "score", 0.0, len(criteria) - 1)
            expected_score = math.fsum(int(key) * probability
                                       for key, probability in probabilities.items())
            if not math.isclose(score, expected_score, rel_tol=0.0, abs_tol=1e-5):
                raise ValueError("Invalid Jev response: Score does not match its weighted probabilities.")
    return response


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise JevClientError("Jev request blocked: HTTP redirect.")


def _http_transport(body: dict, headers: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    opener = urllib.request.build_opener(_NoRedirects())
    with opener.open(request, timeout=timeout) as response:
        return json.load(response)


class LiveJevClient:
    """Explicit live adapter with a per-instance attempt budget and no retries.

    An injected ``transport(body, headers, timeout)`` returns a parsed response
    dictionary. It is called once per evaluate attempt. ``calls`` includes failed
    transport attempts. Construction reads TYPESAFE_API_KEY only when api_key is
    None, and fails before any network activity if no key is present.
    """

    def __init__(self, model: str = MODEL, timeout: float = 30,
                 max_calls: int = 30, transport: Transport | None = None,
                 api_key: str | None = None):
        if model != MODEL:
            raise ValueError(f"This experiment requires model {MODEL}.")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ValueError("Jev timeout must be a positive finite number.")
        try:
            timeout_value = float(timeout)
        except (OverflowError, ValueError):
            raise ValueError("Jev timeout must be a positive finite number.") from None
        if not math.isfinite(timeout_value) or timeout_value <= 0:
            raise ValueError("Jev timeout must be a positive finite number.")
        if isinstance(max_calls, bool) or not isinstance(max_calls, int) or max_calls < 1:
            raise ValueError("Jev max_calls must be a positive integer.")
        key = os.environ.get("TYPESAFE_API_KEY", "") if api_key is None else api_key
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Set TYPESAFE_API_KEY before selecting live Jev mode.")
        if any(character.isspace() for character in key):
            raise ValueError("The Jev API key must not contain whitespace.")
        if transport is not None and not callable(transport):
            raise ValueError("Jev transport must be callable.")
        self.model = model
        self.timeout = timeout_value
        self.max_calls = max_calls
        self.calls = 0
        self._api_key = key
        self._transport = _http_transport if transport is None else transport

    def evaluate(self, state: dict, questions: dict) -> dict:
        if not isinstance(state, dict):
            raise ValueError("Jev state must be a dictionary.")
        _validate_questions(questions)
        body = {"model": self.model, "state": state, "questions": questions}
        try:
            json.dumps(body, allow_nan=False)
        except (ValueError, TypeError, OverflowError):
            raise ValueError("Jev request must contain valid finite JSON values.") from None
        if self.calls >= self.max_calls:
            raise ValueError("Jev call budget exhausted; no additional request was sent.")
        headers = {"Authorization": f"Bearer {self._api_key}",
                   "Content-Type": "application/json", "Accept": "application/json"}
        self.calls += 1
        try:
            response = self._transport(body, headers, self.timeout)
        except urllib.error.HTTPError as error:
            status = error.code if isinstance(error.code, int) and 100 <= error.code <= 599 else "unknown"
            error.close()
            raise JevClientError(f"Jev request failed (HTTP {status}); no automatic retry was sent.") from None
        except JevClientError:
            raise JevClientError("Jev request failed; redirects are blocked and no automatic retry was sent.") from None
        except Exception:
            raise JevClientError("Jev transport failed; no automatic retry was sent.") from None
        return validate_response(response, questions)
