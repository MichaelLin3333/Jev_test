from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path

from .model import digest, stable_json, stamp, utc_now


class Archive:
    def __init__(self, directory: str | Path, mode: str):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory / "news.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
            mode TEXT NOT NULL, status TEXT NOT NULL, config_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS requests (
            id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
            provider TEXT NOT NULL, discovery_id TEXT NOT NULL, url TEXT NOT NULL,
            requested_at TEXT NOT NULL, retrieved_at TEXT NOT NULL,
            status_code INTEGER, error TEXT, raw_path TEXT, body_sha256 TEXT);
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, provider TEXT NOT NULL, provider_key TEXT NOT NULL,
            url TEXT NOT NULL, UNIQUE(provider, provider_key));
        CREATE TABLE IF NOT EXISTS versions (
            id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
            content_hash TEXT NOT NULL, payload_json TEXT NOT NULL,
            first_observed_at TEXT NOT NULL, UNIQUE(document_id, content_hash));
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
            version_id TEXT NOT NULL REFERENCES versions(id),
            request_id TEXT NOT NULL REFERENCES requests(id),
            observed_at TEXT NOT NULL, discovery_id TEXT NOT NULL,
            provider_seen_at TEXT,
            UNIQUE(request_id, document_id, version_id));
        CREATE INDEX IF NOT EXISTS observations_cutoff ON observations(observed_at);
        CREATE TABLE IF NOT EXISTS checkpoints (key TEXT PRIMARY KEY, covered_until TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS query_runs (
            id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
            provider TEXT NOT NULL, discovery_id TEXT NOT NULL,
            window_start TEXT NOT NULL, window_end TEXT NOT NULL,
            status TEXT NOT NULL, normalized_count INTEGER NOT NULL, detail TEXT);
        """)
        columns = {row["name"] for row in self.db.execute("PRAGMA table_info(requests)")}
        if "response_headers_json" not in columns:
            self.db.execute("ALTER TABLE requests ADD COLUMN response_headers_json TEXT NOT NULL DEFAULT '{}'")
        existing = self.db.execute("SELECT value FROM settings WHERE key='mode'").fetchone()
        if existing and existing["value"] != mode:
            self.db.close()
            raise ValueError("Synthetic and live data must use separate archive directories")
        self.db.execute("INSERT OR IGNORE INTO settings VALUES ('mode', ?)", (mode,))
        self.db.commit()
        self.mode = mode

    def close(self):
        self.db.close()

    def start_run(self, config: dict, started_at=None) -> str:
        run_id = uuid.uuid4().hex
        self.db.execute("INSERT INTO runs VALUES (?, ?, NULL, ?, 'running', ?)",
                        (run_id, started_at or stamp(utc_now()), self.mode, stable_json(config)))
        self.db.commit()
        return run_id

    def finish_run(self, run_id: str, status: str):
        self.db.execute("UPDATE runs SET finished_at=?, status=? WHERE id=?",
                        (stamp(utc_now()), status, run_id))
        self.db.commit()

    def record_request(self, run_id: str, provider: str, discovery_id: str,
                       url: str, requested_at: str, retrieved_at: str,
                       status_code: int | None, body: bytes | None,
                       error: str | None = None, response_headers: dict | None = None) -> str:
        request_id = uuid.uuid4().hex
        raw_path = None
        body_hash = None
        if body is not None:
            relative = Path("raw") / run_id / f"{request_id}.response"
            absolute = self.directory / relative
            absolute.parent.mkdir(parents=True, exist_ok=True)
            # Preserve bytes even for malformed JSON, HTTP errors and throttling.
            with absolute.open("xb") as stream:
                stream.write(body)
            raw_path = relative.as_posix()
            body_hash = hashlib.sha256(body).hexdigest()
        self.db.execute("INSERT INTO requests "
                        "(id, run_id, provider, discovery_id, url, requested_at, retrieved_at, "
                        "status_code, error, raw_path, body_sha256, response_headers_json) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (request_id, run_id, provider, discovery_id, url, requested_at,
                         retrieved_at, status_code, error, raw_path, body_hash,
                         stable_json(response_headers or {})))
        self.db.commit()
        return request_id

    def ingest(self, document: dict, request_id: str, discovery_id: str,
               observed_at: str) -> bool:
        document_id = digest(document["provider"] + "\0" + document["provider_key"])
        payload = dict(document)
        provider_seen = payload.pop("provider_seen_at", None)
        # Query matches and observation times are provenance, not new content.
        payload_json = stable_json(payload)
        content_hash = digest(payload_json)
        version_id = digest(document_id + "\0" + content_hash)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO documents VALUES (?, ?, ?, ?)",
                            (document_id, document["provider"], document["provider_key"],
                             document["url"]))
            inserted = self.db.execute(
                "INSERT OR IGNORE INTO versions VALUES (?, ?, ?, ?, ?)",
                (version_id, document_id, content_hash, payload_json, observed_at)).rowcount
            self.db.execute(
                "INSERT OR IGNORE INTO observations "
                "(document_id, version_id, request_id, observed_at, discovery_id, provider_seen_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (document_id, version_id, request_id, observed_at, discovery_id, provider_seen))
        return bool(inserted)

    def checkpoint(self, key: str) -> str | None:
        row = self.db.execute("SELECT covered_until FROM checkpoints WHERE key=?", (key,)).fetchone()
        return row["covered_until"] if row else None

    def query_count(self, run_id: str, provider: str, discovery_id: str) -> int:
        return self.db.execute(
            "SELECT COUNT(DISTINCT o.document_id) FROM observations o "
            "JOIN requests r ON r.id=o.request_id "
            "WHERE r.run_id=? AND r.provider=? AND o.discovery_id=?",
            (run_id, provider, discovery_id)).fetchone()[0]

    def query_result(self, run_id, provider, discovery_id, start, end,
                     status, count, detail=None, checkpoint_key=None):
        with self.db:
            self.db.execute("INSERT INTO query_runs "
                            "(run_id, provider, discovery_id, window_start, window_end, status, "
                            "normalized_count, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (run_id, provider, discovery_id, start, end, status, count, detail))
            if status == "ok" and checkpoint_key:
                self.db.execute(
                    "INSERT INTO checkpoints VALUES (?, ?) ON CONFLICT(key) DO UPDATE "
                    "SET covered_until=MAX(checkpoints.covered_until, excluded.covered_until)",
                    (checkpoint_key, end))

    def snapshot(self, as_of: str):
        # Rank observations, not version creation dates: A -> B -> A is a real reversion.
        rows = self.db.execute("""
        WITH available AS (
            SELECT o.*, ROW_NUMBER() OVER (
                PARTITION BY o.document_id ORDER BY o.observed_at DESC, o.id DESC) AS rank
            FROM observations o WHERE observed_at <= ?
        )
        SELECT a.*, v.payload_json, v.content_hash, v.first_observed_at,
               r.raw_path, r.body_sha256
        FROM available a JOIN versions v ON v.id=a.version_id
        JOIN requests r ON r.id=a.request_id WHERE a.rank=1 ORDER BY a.document_id
        """, (as_of,)).fetchall()
        for row in rows:
            payload = json.loads(row["payload_json"])
            provenance = self.db.execute(
                "SELECT MIN(observed_at) AS first_seen, MAX(observed_at) AS last_seen "
                "FROM observations WHERE document_id=? AND observed_at<=?",
                (row["document_id"], as_of)).fetchone()
            matches = self.db.execute(
                "SELECT DISTINCT discovery_id FROM observations "
                "WHERE document_id=? AND observed_at<=? ORDER BY discovery_id",
                (row["document_id"], as_of)).fetchall()
            yield {
                "document_id": row["document_id"], "version_id": row["version_id"],
                "archive_mode": self.mode, "as_of": as_of, **payload,
                "provider_seen_at": row["provider_seen_at"],
                "first_seen_at": provenance["first_seen"],
                "last_seen_at": provenance["last_seen"],
                "version_first_observed_at": row["first_observed_at"],
                "snapshot_observed_at": row["observed_at"],
                "discovery_ids": [match["discovery_id"] for match in matches],
                "raw_response_path": row["raw_path"],
                "raw_response_sha256": row["body_sha256"],
                "content_hash": row["content_hash"],
            }

    def status(self) -> dict:
        counts = {table: self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("documents", "versions", "observations", "requests", "runs")}
        last = self.db.execute("SELECT * FROM runs ORDER BY started_at DESC, rowid DESC LIMIT 1").fetchone()
        latest_queries = []
        if last:
            latest_queries = [dict(row) for row in self.db.execute(
                "SELECT provider, discovery_id, status, normalized_count, detail FROM query_runs "
                "WHERE run_id=? ORDER BY id", (last["id"],))]
        return {"archive_mode": self.mode, **counts,
                "last_run": dict(last) if last else None, "last_query_results": latest_queries}
