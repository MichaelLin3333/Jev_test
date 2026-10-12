from __future__ import annotations

import json
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .model import stamp, utc_now


class FetchError(RuntimeError):
    pass


@dataclass
class Response:
    request_id: str
    observed_at: str
    payload: object


class HttpClient:
    def __init__(self, archive, run_id, timeout=20, retries=2, max_requests=60,
                 transport=None, sleep=time.sleep, clock=utc_now,
                 gdelt_interval=5.2):
        self.archive, self.run_id = archive, run_id
        self.timeout, self.retries = timeout, retries
        self.max_requests, self.used = max_requests, 0
        self.transport = transport or self._transport
        self.sleep, self.clock = sleep, clock
        self.intervals = {"api.gdeltproject.org": gdelt_interval, "data.sec.gov": 0.2}
        self.last_request = {}

    def _transport(self, url, headers):
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read(10_000_001)
                if len(body) > 10_000_000:
                    raise FetchError("Response exceeded the 10 MB draft limit")
                return response.status, body, dict(response.headers.items())
        except HTTPError as error:
            return error.code, error.read(1_000_000), dict(error.headers.items())

    def get(self, provider: str, discovery_id: str, url: str, headers=None) -> Response:
        headers = {"User-Agent": "jev-news-pipeline/0.1 (research draft)",
                   "Accept": "application/json", **(headers or {})}
        host = urlsplit(url).hostname
        for attempt in range(self.retries + 1):
            if self.used >= self.max_requests:
                raise FetchError("Run request budget exhausted; coverage is incomplete")
            interval = self.intervals.get(host, 0)
            elapsed = time.monotonic() - self.last_request.get(host, -1e9)
            if elapsed < interval:
                self.sleep(interval - elapsed)
            requested = stamp(self.clock())
            self.used += 1
            self.last_request[host] = time.monotonic()
            code, body, problem = None, None, None
            response_headers = {}
            try:
                received = self.transport(url, headers)
                code, body = received[:2]
                if len(received) == 3:
                    response_headers = {k.lower(): v for k, v in received[2].items()
                                        if k.lower() in {"retry-after", "content-type", "etag", "last-modified"}}
                if code != 200:
                    problem = f"HTTP {code}"
            except (URLError, OSError, TimeoutError, FetchError) as error:
                problem = f"{type(error).__name__}: {error}"
            observed = stamp(self.clock())
            payload = None
            if problem is None:
                try:
                    payload = json.loads(body.decode("utf-8-sig"))
                except (ValueError, UnicodeError) as error:
                    problem = f"Invalid JSON: {error}"
            request_id = self.archive.record_request(
                self.run_id, provider, discovery_id, url, requested, observed, code, body,
                problem, response_headers)
            if problem is None:
                return Response(request_id, observed, payload)
            retryable = code is None or code == 429 or (code is not None and code >= 500)
            if attempt >= self.retries or not retryable:
                raise FetchError(problem)
            wait = min(2 ** attempt, 8)
            retry_after = response_headers.get("retry-after")
            if retry_after:
                try:
                    wait = max(wait, float(retry_after))
                except ValueError:
                    try:
                        wait = max(wait, (parsedate_to_datetime(retry_after) - self.clock()).total_seconds())
                    except (TypeError, ValueError, OverflowError):
                        pass
            if wait > 60:
                raise FetchError(f"{problem}; provider requests a wait over 60 seconds; retry a later batch")
            self.sleep(wait)
        raise FetchError("Request failed")
