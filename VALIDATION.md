# Draft validation — October 9, 2026

## Jev demo update — October 10, 2026

- **52 offline tests passed:** 21 collector tests, 15 Jev API/client tests and 16 staged-analysis tests. The Windows sandbox denied test temporary-directory access, so the suite was rerun with the required permission and passed.
- **Both synthetic replay cutoffs ran end to end.** Six unique events; ten scripted evaluation calls per report. The original customer budget is USD 24bn versus a USD 20bn prior plan (+20%). The correction is USD 21bn (+5%). Repeated documents remain one supplied event.
- **Missing-key live path verified.** Selecting the live backend without TYPESAFE_API_KEY stops explicitly before any model call. No actual Jev inference, paid call, or new live-news request was made during this update.
- **API contract checked against current official documentation.** The real adapter pins jev-1.13.0, stages dependencies in separate calls, validates responses and never falls back silently to scripted output.
- **Report artifacts created.** HTML report, frozen inputs, question registry, request payloads without credentials, and explicitly scripted response distributions. The in-app browser blocks local file URLs, so visual browser inspection was unavailable; report contents and relative links were checked locally.
- **Scope remains experimental.** Synthetic grouping and exposures are supplied, not learned. Real archives only deduplicate document identities. Economic channels are conditional interpretations; stock-return probabilities and price targets remain null.
- **Still standalone.** No SimpliEarn integration or background process.

The newer `jev-news-jev-demo.zip` includes the updated code, docs, fixtures, tests and before/after example report folders. It excludes SQLite archives, raw feed responses, credentials and caches. The original `jev-news-pipeline-draft.zip` remains the earlier collector-only snapshot.

## Historical pilot update - October 12, 2026

- **Actual Jev inference completed:** 11 conditions across three historical issuer announcements, anonymized pairs, reversed-fact scenarios and two controls. All primary semantic checks passed. A simple word rule also matched all three historical revenue labels.
- **Important weakness identified:** six of nine substantive cases inferred a discount-rate direction without direct supporting rate evidence. Materiality quantities and denominators need clarification. This pilot does not validate stock forecasts or full-stream news selection.
- **24 API attempts total:** 30,408 reported input tokens, approximately $0.001277 at published pricing. Including a full-context allowance for one unmetered invalid response keeps the estimate below $0.004. Actual account billing was not queried.
- **Failure and continuation preserved:** one response failed strict probability validation. Five completed cases were reused unchanged; remaining cases completed in a new run. Raw provider JSON is now retained before validation for future diagnosis. No silent normalization or scripted fallback was used.
- **64 offline tests passed:** the original 52 tests plus 12 historical-harness tests. New checks cover anonymization, exclusion of outcome labels from prompts, counterfactual grounding, timing, budget boundaries and continuation accounting. These tests make no network requests.
- **Credentials absent from saved artifacts:** a local scan found no API-key prefix in project text files or reports. The supplied credential was not persisted to files or environment settings.

Read [HISTORICAL_PILOT_REPORT.md](HISTORICAL_PILOT_REPORT.md) for sources, exact results, costs, limits and the next experiment. Earlier dated notes below describe the state at those earlier checks.

## Initial collector validation

- **21 offline tests passed.** Tests cover replay cutoffs, revision/reversion selection, duplicate discovery, raw response retention, malformed data, retry behavior including Retry-After, request budgets, result-cap splitting, coverage checkpoints, SEC metadata, and synthetic/live separation.
- **Offline demo verified end to end.** Three unique documents and four unique content versions. Re-running keeps those counts unchanged. An export at 12:20 UTC contains two original headlines; an export at 12:40 UTC contains the revised headline and the synthetic filing metadata, three documents total.
- **Live GDELT attempted.** The first sandbox request failed DNS resolution. A permitted request outside the sandbox reached GDELT and returned HTTP 429. The response was archived, coverage recorded as partial, and no successful checkpoint advanced. No real news records were collected during this check.
- **SEC live retrieval not attempted.** It requires the user's identifying SEC_USER_AGENT value; missing contact settings and response parsing are covered by offline tests.
- **No background collector is running.** Foreground polling is available through the documented --watch option.
- **SimpliEarn was not modified.** All draft files, synthetic exports, and local archives are in this standalone directory.

## Included example exports

- exports/demo-before.jsonl — synthetic earlier snapshot.
- exports/demo-after.jsonl — synthetic later snapshot.

The ZIP contains source code, config, fixtures, tests, this note, and those synthetic examples. It excludes live/local databases, raw network responses, and Python caches.

## Remaining validation

A successful public-feed retrieval and a multi-day coverage audit are still needed before this collector can be considered operational. Full article/filing text, real semantic event grouping, a larger held-out Jev evaluation and measured market-return forecasts remain future extensions. Actual inference on curated historical summaries is now complete, as documented in the October 12 update.
