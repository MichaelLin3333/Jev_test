from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from jev_news.collect import CoverageError, collect, gdelt_window, validate_config
from jev_news.http import FetchError, HttpClient
from jev_news.model import canonical_url, gdelt_document, parse_time, sec_documents, stamp
from jev_news.store import Archive

T0 = "2026-10-09T12:00:00.000000Z"
T1 = "2026-10-09T12:15:00.000000Z"
T2 = "2026-10-09T12:30:00.000000Z"


def article(title="Original", suffix="one"):
    return {"url": f"https://example.org/{suffix}?utm_source=test", "title": title,
            "seendate": "20261009T115000Z", "language": "English",
            "domain": "example.org", "sourcecountry": "United States"}


def sec_payload(acceptance="2026-10-09T11:45:00Z"):
    result = {"cik": "1045810", "filings": {"recent": {
        "accessionNumber": ["0001045810-26-000001"], "form": ["8-K"],
        "filingDate": ["2026-10-09"], "primaryDocument": ["example.htm"]}}}
    if acceptance is not None:
        result["filings"]["recent"]["acceptanceDateTime"] = [acceptance]
    return result


COMPANY = {"ticker": "NVDA", "name": "NVIDIA", "cik": "1045810"}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.archive = Archive(self.temp.name, "synthetic")
        self.run = self.archive.start_run({"test": True}, T0)

    def tearDown(self):
        self.archive.close()
        self.temp.cleanup()

    def response(self, payload, at=T0, discovery="test", provider="gdelt"):
        return self.archive.record_request(
            self.run, provider, discovery, "fixture://test", at, at, 200,
            json.dumps(payload).encode("utf-8"))

    def ingest(self, item, at=T0, discovery="test"):
        request = self.response(item, at, discovery)
        return self.archive.ingest(gdelt_document(item), request, discovery, at)

    def client(self, transport, budget=60):
        return HttpClient(self.archive, self.run, transport=transport,
                          retries=0, max_requests=budget, sleep=lambda _: None,
                          gdelt_interval=0, clock=lambda: parse_time(T0))

    def test_repeated_discovery_preserves_one_version_and_query_provenance(self):
        self.ingest(article(), T0, "direct")
        self.ingest(article(), T1, "industry")
        stats = self.archive.status()
        self.assertEqual((stats["documents"], stats["versions"], stats["observations"]), (1, 1, 2))
        exported = list(self.archive.snapshot(T2))[0]
        self.assertEqual(exported["discovery_ids"], ["direct", "industry"])
        self.assertEqual(exported["first_seen_at"], T0)

    def test_replay_does_not_see_future_revision_or_future_discovery(self):
        self.ingest(article(), T0, "direct")
        self.ingest(article("Revised"), T2, "industry")
        before = list(self.archive.snapshot(T1))[0]
        after = list(self.archive.snapshot(T2))[0]
        self.assertEqual(before["title"], "Original")
        self.assertEqual(before["last_seen_at"], T0)
        self.assertEqual(before["discovery_ids"], ["direct"])
        self.assertEqual(after["title"], "Revised")

    def test_content_reversion_uses_latest_observation_not_version_creation(self):
        self.ingest(article("A"), T0)
        self.ingest(article("B"), T1)
        self.ingest(article("A"), T2)
        self.assertEqual(list(self.archive.snapshot(T2))[0]["title"], "A")
        self.assertEqual(self.archive.status()["versions"], 2)

    def test_discovery_time_is_never_mislabeled_as_publication_time(self):
        normalized = gdelt_document(article())
        self.assertIsNone(normalized["published_at"])
        self.assertEqual(normalized["provider_seen_at"], "2026-10-09T11:50:00.000000Z")
        self.assertEqual(normalized["text_type"], "headline")
        with self.assertRaises(ValueError):
            parse_time("2026-10-09")
        with self.assertRaises(ValueError):
            parse_time("2026-10-09T12:00:00")

    def test_tracking_is_removed_without_destroying_meaningful_url_parameters(self):
        self.assertEqual(
            canonical_url("https://EXAMPLE.org/story?id=2&utm_source=x&lang=en#top"),
            "https://example.org/story?id=2&lang=en")
        self.assertNotEqual(canonical_url("https://example.org/story?id=1"),
                            canonical_url("https://example.org/story?id=2"))
        with self.assertRaises(ValueError):
            canonical_url("file:///secrets")

    def test_provider_observation_changes_do_not_create_content_versions(self):
        first = article()
        second = article()
        second["seendate"] = "20261009T120000Z"
        self.ingest(first, T0)
        self.ingest(second, T1)
        self.assertEqual(self.archive.status()["versions"], 1)

    def test_response_bytes_and_hash_are_preserved(self):
        raw = b'{"unusual": " spacing kept " }\n'
        request_id = self.archive.record_request(
            self.run, "gdelt", "test", "fixture://test", T0, T0, 200, raw)
        row = self.archive.db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
        self.assertEqual((Path(self.temp.name) / row["raw_path"]).read_bytes(), raw)
        import hashlib
        self.assertEqual(row["body_sha256"], hashlib.sha256(raw).hexdigest())

    def test_invalid_json_is_an_archived_failure_not_an_empty_news_batch(self):
        client = self.client(lambda *_: (200, b"Please slow down"))
        with self.assertRaises(FetchError):
            client.get("gdelt", "test", "https://api.gdeltproject.org/test")
        row = self.archive.db.execute("SELECT * FROM requests").fetchone()
        self.assertIn("Invalid JSON", row["error"])
        self.assertEqual((Path(self.temp.name) / row["raw_path"]).read_bytes(), b"Please slow down")

    def test_retry_archives_failed_and_successful_attempts(self):
        responses = iter([(429, b"rate limit"), (200, b'{"articles": []}')])
        client = self.client(lambda *_: next(responses))
        client.retries = 1
        client.get("gdelt", "test", "https://api.gdeltproject.org/test")
        self.assertEqual(self.archive.status()["requests"], 2)

    def test_retry_after_is_respected_and_preserved(self):
        responses = iter([(429, b"wait", {"Retry-After": "12"}),
                          (200, b'{"articles": []}', {})])
        client = self.client(lambda *_: next(responses))
        waits = []
        client.sleep = waits.append
        client.retries = 1
        client.get("gdelt", "test", "https://api.gdeltproject.org/test")
        self.assertIn(12, waits)
        first = self.archive.db.execute("SELECT response_headers_json FROM requests LIMIT 1").fetchone()
        self.assertEqual(json.loads(first[0])["retry-after"], "12")

    def test_long_retry_after_stops_batch_instead_of_retrying_early(self):
        client = self.client(lambda *_: (429, b"wait", {"Retry-After": "120"}))
        client.retries = 1
        with self.assertRaisesRegex(FetchError, "retry a later batch"):
            client.get("gdelt", "test", "https://api.gdeltproject.org/test")
        self.assertEqual(client.used, 1)

    def test_cap_triggers_smaller_windows_and_retains_unique_documents(self):
        payloads = iter([
            {"articles": [article("A", "a"), article("B", "b")]},
            {"articles": [article("A", "a")]},
            {"articles": [article("C", "c")]},
        ])
        client = self.client(lambda *_: (200, json.dumps(next(payloads)).encode()))
        end = parse_time(T0)
        gdelt_window(client, self.archive, {"id": "test", "query": "chips"},
                     end - timedelta(hours=1), end, cap=2)
        self.assertEqual(client.used, 3)
        self.assertEqual(self.archive.status()["documents"], 3)

    def test_unresolved_cap_is_visible_and_keeps_checkpoint_unchanged(self):
        client = self.client(lambda *_: (200, json.dumps({"articles": [article()]}).encode()))
        with self.assertRaises(CoverageError):
            gdelt_window(client, self.archive, {"id": "test", "query": "chips"},
                         parse_time(T0) - timedelta(minutes=15), parse_time(T0), cap=1)
        self.assertEqual(self.archive.status()["documents"], 1)

    def test_partial_batch_keeps_valid_rows_but_does_not_advance_checkpoint(self):
        config = {"gdelt": {"queries": [{"id": "test", "query": "chips"}]},
                  "sec": {"enabled": False}}
        valid = article()
        client = self.client(lambda *_: (200, json.dumps({"articles": [valid, {"title": "bad"}]}).encode()))
        rows = collect(config, self.archive, client, self.run, parse_time(T0), sources=("gdelt",))
        self.assertEqual(rows[0]["status"], "partial")
        self.assertEqual(rows[0]["normalized_count"], 1)
        self.assertEqual(self.archive.db.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0], 0)

    def test_failed_next_run_preserves_previous_successful_checkpoint(self):
        config = {"gdelt": {"queries": [{"id": "test", "query": "chips"}]}}
        good = self.client(lambda *_: (200, b'{"articles": []}'))
        collect(config, self.archive, good, self.run, parse_time(T0), sources=("gdelt",))
        previous = self.archive.db.execute("SELECT covered_until FROM checkpoints").fetchone()[0]
        bad = self.client(lambda *_: (503, b"outage"))
        collect(config, self.archive, bad, self.run, parse_time(T2), sources=("gdelt",))
        self.assertEqual(self.archive.db.execute("SELECT covered_until FROM checkpoints").fetchone()[0],
                         previous)

    def test_request_budget_bounds_provider_fanout(self):
        client = self.client(lambda *_: (200, b'{"articles": []}'), budget=1)
        client.get("gdelt", "test", "https://api.gdeltproject.org/test")
        with self.assertRaises(FetchError):
            client.get("gdelt", "test", "https://api.gdeltproject.org/test")
        self.assertEqual(client.used, 1)

    def test_sec_date_only_metadata_does_not_invent_a_timestamp_or_body(self):
        result = sec_documents(sec_payload(None), COMPANY, ["8-K"],
                               parse_time(T0) - timedelta(days=1), parse_time(T0))
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["published_at"])
        self.assertIsNone(result[0]["text"])
        self.assertEqual(result[0]["metadata"]["timestamp_precision"], "date")

    def test_sec_checks_identity_array_alignment_and_file_paths(self):
        with self.assertRaises(ValueError):
            sec_documents(sec_payload(), {**COMPANY, "cik": "1"}, ["8-K"],
                          parse_time(T0) - timedelta(days=1), parse_time(T0))
        broken = sec_payload()
        broken["filings"]["recent"]["form"] = []
        with self.assertRaises(ValueError):
            sec_documents(broken, COMPANY, ["8-K"],
                          parse_time(T0) - timedelta(days=1), parse_time(T0))
        broken = sec_payload()
        broken["filings"]["recent"]["primaryDocument"] = ["../outside.htm"]
        with self.assertRaises(ValueError):
            sec_documents(broken, COMPANY, ["8-K"],
                          parse_time(T0) - timedelta(days=1), parse_time(T0))

    def test_sec_contact_is_required_before_a_network_request(self):
        client = self.client(lambda *_: self.fail("SEC request sent without contact"))
        with patch.dict("os.environ", {}, clear=True):
            rows = collect({"companies": [COMPANY]}, self.archive, client, self.run,
                           parse_time(T0), sources=("sec",))
        self.assertEqual(rows[0]["status"], "partial")
        self.assertEqual(client.used, 0)

    def test_synthetic_and_live_archives_cannot_mix(self):
        with self.assertRaises(ValueError):
            Archive(self.temp.name, "live")

    def test_duplicate_query_ids_and_zero_lookback_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_config({"gdelt": {"queries": [
                {"id": "same", "query": "a"}, {"id": "same", "query": "b"}]}})
        with self.assertRaises(ValueError):
            collect({}, self.archive, self.client(lambda *_: None), self.run,
                    parse_time(T0), lookback_hours=0)


if __name__ == "__main__":
    unittest.main()
