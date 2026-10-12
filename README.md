# Jev news pipeline — standalone draft

A small, keyless starting point for the Jev news experiment. This folder is independent of SimpliEarn. It uses Python 3.11+ and the standard library; no dependency installation is needed.

The draft collects:
- **GDELT discovery:** headlines, URLs, language, source country, and provider discovery time.
- **SEC recent filing indexes:** accession, form, acceptance timestamp when available, and a link to the primary filing for NVIDIA, Microsoft, and Apple.

It archives original response bytes, deduplicates documents, retains changed versions, records every discovery, and exports the latest version actually observed by a chosen cutoff. A basic Jev interpretation demo is now included, with an offline fixture backend and an explicitly selected live API adapter. Article/filing bodies, automatic event clustering and stock prices remain future work.

## Historical feasibility pilot

A live Jev pilot on three classic issuer announcements is complete. Revenue interpretation passed the historical, anonymized and reversed-fact checks; two controls also behaved as intended. A simple word rule matched all three historical signs too, and the audit found unsupported discount-rate judgments. These results do not validate stock-return prediction. See [the full pilot report](HISTORICAL_PILOT_REPORT.md) for results, sources, limitations and estimated cost below $0.004.

To prepare a new protocol without API calls:

```powershell
python -m jev_news.historical_pilot
```

Actual paid inference requires `--live` and a locally available `TYPESAFE_API_KEY`. The pilot defaults to at most 33 API attempts and a $0.10 published-price reservation. Re-running is unnecessary to inspect the saved results.

## Run the Jev demo

```powershell
python -m jev_news jev-demo
```

This seeds eight synthetic documents into a separate `jev-demo-data` archive and writes a new HTML report under `reports/jev`. It needs no key or network. The model distributions are hand-authored fixtures, clearly marked as scripted; this demonstrates orchestration, not Jev accuracy. See [JEV_DEMO.md](JEV_DEMO.md) for the decision flow, correction replay and real API setup.

The report follows six unique events through claim/relevance checks, economic channels and a conditional exposure-scale assessment. It includes favorable customer-demand evidence, adverse policy evidence, an unverified rumor, a vague headline, an unrelated story and filing metadata. Stock-return forecasts remain unestimated.

## Try the offline demo first

Open a terminal in this folder, then run:

```powershell
python -m jev_news demo
python -m jev_news status --data demo-data
python -m jev_news export --data demo-data --as-of "2026-10-09T12:20:00Z" --output exports/demo-before.jsonl
python -m jev_news export --data demo-data --as-of "2026-10-09T12:40:00Z" --output exports/demo-after.jsonl
```

Every demo story is explicitly synthetic. The demo contains a repeated discovery, a later revised headline, and a fake filing metadata record. Compare the two exports: the first must not reveal the later revision or filing. Re-running the demo leaves document/version counts unchanged while recording new sightings. Demo data and live data cannot be written into the same archive.

## Collect a small live news batch

Start with one query and a short window:

```powershell
python -m jev_news collect --sources gdelt --query nvidia --lookback-hours 1 --max-requests 4
python -m jev_news status
python -m jev_news export --output exports/latest.jsonl
```

For the configured direct-company, industry-dependency, and macro-policy searches:

```powershell
python -m jev_news collect --sources gdelt
```

The default first run looks back 24 hours. Later runs resume each successful query with a 60-minute overlap. An explicit `--lookback-hours 24` forces reconciliation/backfill instead of using the saved checkpoint. Overlap reduces, but does not eliminate, late-arrival gaps. Occasionally reconcile a longer window and inspect coverage.

GDELT calls are spaced at least 5.2 seconds apart. Retryable transport errors, HTTP 429, and server errors retry with bounded backoff, respecting a valid Retry-After header. A provider wait exceeding 60 seconds stops that query for a later batch rather than retrying early. Defaults: 20-second request timeout, two retries, and 60 total HTTP attempts per batch. Large first runs can take several minutes. Provider access and completeness still require a live audit.

## Add SEC metadata

SEC requests require an identifying user agent containing your project name and contact email. Set your own value in the current terminal:

```powershell
$env:SEC_USER_AGENT = "YourResearchProject your-contact@example.com"
python -m jev_news collect --sources sec
```

Replace that example address with your actual contact address. The value is used in SEC request headers and is not written into the config or exported records. The collector limits SEC requests below the published aggregate limit.

Run both sources after setting the contact:

```powershell
python -m jev_news collect
```

Without the contact setting, GDELT can still collect, while SEC is explicitly reported incomplete. This is not represented as a successful zero-filings result.

To repeat in the foreground every 15 minutes:

```powershell
python -m jev_news collect --watch --interval-minutes 15
```

Keep the terminal running; Ctrl+C stops it. This draft does not install a service or scheduled task. Batches do not overlap; the interval starts after a batch finishes. Use only one writer process per archive directory in this draft.

## Files produced

```text
data/
  news.sqlite3               Document versions, observations, requests, query coverage, checkpoints
  raw/<run-id>/*.response   Original response bytes, including malformed/error responses when received
exports/
  latest.jsonl              One observed document version per provider identity at the cutoff
```

Raw files are hashed and never overwritten. Query configuration is captured per run. JSONL exports include raw-response references, content hashes, provenance, archive mode, and the export cutoff. Keep the database and raw directory together.

The same URL can produce multiple versions if normalized content changes. Duplicate discoveries through different queries do not create new versions. Known tracking parameters are removed, but meaningful URL parameters are retained. This is **document deduplication**, not semantic event clustering; different publishers covering one event remain separate documents.

## Timing and evidence rules

- GDELT's `seendate` is saved as `provider_seen_at`. It is **not** substituted for an article publication timestamp; `published_at` stays null.
- SEC acceptance timestamps are preserved when timezone-qualified. If only a filing date exists, publication time stays null and date precision is recorded.
- `first_seen_at` and `snapshot_observed_at` are local response-receipt times. A news item's publisher/discovery time does not imply this collector had it then.
- `version_first_observed_at` identifies the first observation of that content version. A later reversion to older text is selected using the observation ledger, not version creation order.
- Retrospective downloads are available only from when the collector received them. They must not be presented as prospective inputs at their historical publication time.
- Exports filter observations and query provenance by the cutoff; later revisions and later sightings are excluded.
- GDELT records are marked `headline`; SEC records are marked `filing_metadata`. There is no implication that full article or filing text has been archived.
- Company names in collection queries are discovery hints, not validated company relevance labels.

## Coverage and failure behavior

If a GDELT result reaches 250 records, the collector subdivides the time window. It stops splitting at approximately 15-minute windows. A still-saturated window, malformed article, request-budget exhaustion, or provider failure makes that query **partial**. Valid records already received remain archived, and the successful-coverage checkpoint does not advance.

Counts in query reports are distinct document identities retained for that query during the batch, including valid rows retained before a partial failure. The same document can legitimately appear in several query reports.

SEC collects only the submissions API's `recent` arrays and selected forms. Historical submissions files and filing bodies are not fetched. A requested range older than those arrays is explicitly incomplete. Selected forms are 8-K, 10-K, and 10-Q; amend the config if amendments or other forms are needed.

A checkpoint means the configured provider query completed without a detected gap. It is not a guarantee of all news on the internet, publisher completeness, or provider accuracy. Very late arrivals outside the overlap can still be missed.

Exit codes: `0` complete selected batch/export; `2` partial collection; `1` configuration/local error; `130` interrupted. An interrupted run is recorded as failed; partial observations are retained. Review `status` rather than treating missing data as no news.

## Configuration

Edit `config.example.json` to change companies, CIKs, forms, queries, and overlap. GDELT queries have stable IDs; changing the actual query creates a separate checkpoint. Company CIKs are explicit so ticker/entity resolution is not silently delegated to a search result.

Default search lanes:
- Direct: NVIDIA, Microsoft, Apple products/names.
- Industry dependencies: semiconductors, packaging, AI infrastructure.
- Macro/policy: export controls, interest rates, inflation.

These are a bounded pilot, not an exhaustive market-news sample. A random background sample and more exposure-specific queries are useful next additions.

## Verification

```powershell
python -m unittest discover -s tests -v
```

Tests cover duplicate discovery, tracking URLs, revisions and content reversions, absence of future information in exports, raw-byte retention, malformed responses, retries, saturated windows, partial-batch checkpoints, SEC identity/timestamp handling, and isolation of synthetic data.

The supplied demo can run completely offline. Automated tests use temporary directories and fake transports; they make no live network requests.

## Next development steps

1. Audit a week of live coverage and provider delays; review missing-text and partial-query counts.
2. Add a paid news adapter only after sampling its text completeness and verifying archival permissions. Keep provider sentiment separate from future Jev labels.
3. Retrieve selected primary filing documents and permitted article text with explicit provenance and text-quality fields.
4. Extend the demo's exact evidence passages and supplied synthetic event grouping to grounded extraction and real semantic event clustering.
5. Repair the channel evidence gates found by the historical pilot, then evaluate Jev on a larger frozen sample with dated company exposure profiles and simple baselines.
6. Add market labels only once the observation clock and price source have been validated.

## Official references

- [GDELT DOC API parameters and result limits](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
- [SEC submissions APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [SEC developer resources and fair access](https://www.sec.gov/about/developer-resources)
