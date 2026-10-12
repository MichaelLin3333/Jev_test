# Jev historical feasibility pilot — October 12, 2026

**The current method passed a small revenue-interpretation test, but it is not yet validated for stock prediction.** Real Jev inference agreed with the intended revenue channel in three classic announcements, preserved those judgments under anonymization, and followed deliberately reversed facts. The same test exposed unsupported valuation-channel inference and unstable materiality interpretation.

This work is standalone; SimpliEarn was not modified. No background collector or inference process remains running.

## What was actually tested

The pinned `jev-1.13.0` model evaluated **11 inputs** using the existing `news-interpretation-0.1.0` question graph:

- Three short, researcher-authored summaries of dated issuer announcements.
- Three matching anonymized summaries.
- Three coherent synthetic scenarios reversing the decisive revenue news.
- Two controls: filing metadata without substantive text, and a clearly unrelated local story.

The source text and expected semantic labels were frozen before inference. The researcher knew these famous historical events; this is a documented feasibility exercise, not a blinded or preregistered scientific experiment. No later stock returns or outcome-report URLs were sent to Jev. Dependencies used separate API calls, and exact transmitted payloads were saved.

The inputs are **curated paraphrases**, not downloaded article bodies or point-in-time feed snapshots. Source availability was reconstructed from dated releases; actual retrieval and inference happened now. This bypasses the data pipeline's real-world retrieval, claim extraction and news-selection problems.

## Historical cases

| Announcement | Jev revenue channel | Probability assigned to that label | Next regular-session stock return |
| --- | --- | --- | --- |
| [NVIDIA, May 24, 2023: AI demand and $11bn next-quarter revenue outlook](https://investor.nvidia.com/news/press-release-details/2023/NVIDIA-Announces-Financial-Results-for-First-Quarter-Fiscal-2024/) | Favorable | 0.98 | [Approximately +24%, May 25](https://www.investing.com/news/stock-market-news/wall-street-ends-higher-as-nvidia-sparks-rush-for-ai-stocks-3090585) |
| [Meta, February 2, 2022: advertising headwinds and weak outlook](https://investor.atmeta.com/investor-news/press-release-details/2022/Meta-Reports-Fourth-Quarter-and-Full-Year-2021-Results/default.aspx) | Adverse | 0.99 | [Approximately −26.4%, February 3](https://www.marketscreener.com/news/latest/Wall-St-ends-winning-run-as-Facebook-forecast-halts-tech-led-recovery-37731510/) |
| [Apple, January 2, 2019: revenue estimate reduced to $84bn from $89–93bn](https://www.apple.com/newsroom/2019/01/letter-from-tim-cook-to-apple-investors/) | Adverse | 1.00 | [Approximately −10%, January 3](https://za.investing.com/news/stock-market-news/us-stockswall-st-plunges-as-factory-data-apple-warning-fuel-slowdown-fears-1379926) |

These probabilities describe Jev's **economic classification**, not the probability that the stock rises or falls. The stock moves are rounded values from contemporary Reuters reporting, not independently calculated price labels. Corresponding S&P 500 moves were +0.88%, −2.44%, and −2.48%; subtracting those would be simple market adjustment, not causal attribution.

The return windows include the overnight reaction. The announcements arrived after the preceding regular-session close, so that earlier close was not an executable entry using the new announcement. This system did not earn these returns.

## Stress tests and baselines

| Endpoint | Result | Interpretation |
| --- | --- | --- |
| Historical primary revenue channel | 3/3 matched | Basic economic sign recognition worked |
| Anonymized revenue channel | 3/3 preserved | Names were not necessary for these decisions |
| Reversed-fact revenue channel | 3/3 reversed as intended | The model responded to changed facts rather than simply retaining the original event sign |
| Metadata / unrelated controls | 2/2 handled correctly | Missing content remained insufficient; unrelated news was excluded |
| Simple direction-word rule on historical cases | 3/3 matched | Jev did not beat this cheap baseline on these obvious examples |
| Majority-adverse historical baseline | 2/3 matched | Three deliberately selected cases do not provide a reliable accuracy estimate |

Anonymous requests removed real company names, tickers, product names, calendar years, source URLs and audit IDs. Financial figures were retained and can still identify famous events. Anonymization is a memory-sensitivity probe; it does not exclude training contamination. The nine substantive inputs share three underlying cases and are not nine independent historical observations.

The reversed Meta scenario intentionally retained the adverse margin fact while reversing the revenue outlook. Jev selected favorable revenue with probability 0.66 and adverse margin, producing mixed combined evidence. Keeping competing channels separate was useful here.

## Problems found

**Discount-rate inference is too permissive.** Six of nine substantive inputs received an adverse or mixed discount-rate direction, even though their supplied text contains no direct rate, yield, financing-cost or risk-premium evidence. The original and anonymized Meta cases, for example, were both labeled adverse on this channel. Weak revenue news does not by itself establish a discount-rate change. Add a separate evidence gate and default to unknown when its requirements fail.

**Materiality needs a precise quantity and denominator.** Apple received an ordinal score of 2.45 with its real identity and 2.12 when anonymized. The leading rubric level shifted from substantial to moderate. These single paired calls do not distinguish identity sensitivity from ordinary run-to-run variation. Its $84bn revision is about 7.7% below the earlier $91bn midpoint, but the current rubric ambiguously mixes the size of the affected exposure with the size of the economic change. Compute the comparable revision in code and distinguish it from total exposed revenue. Do not convert either score into a stock-return magnitude.

**Response validation caught an operational failure.** The first run stopped on one probability distribution that did not satisfy the client's sum-to-one check. It did not normalize the answer, invent a replacement, or fall back to scripted values. The invalid raw response was not retained, so its exact discrepancy cannot be diagnosed. A continuation reused all five completed cases unchanged and finished the remaining inputs. Parsed provider JSON is now captured before validation so a later failure can be inspected. This does not establish that the provider issue is fixed.

## API use and cost

- **24 total API attempts**, including the failed response and continuation; original cap: 33.
- **30,408 reported input tokens** and 3,285 reported output tokens from validated responses.
- **$0.001277136 estimated token charge** for those reported inputs at the [published $0.042/million input-token rate](https://docs.typesafe.ai/models); outputs are free.
- The one failed response has no usable token accounting in the archive. Allowing a full 64,000-token context for that attempt gives a conservative total of **less than $0.004** at the published rate.
- The account's actual billing ledger and remaining balance were not queried. The pilot stayed far below the user's $5 allowance.

Credentials were supplied to the process through hidden input and were not written into project files, request payloads, reports, or environment settings. The key was pasted into the conversation, so it should be replaced after the test.

## How to improve the proposed test

Classic shocks are useful positive controls, but their later return is not a uniquely correct answer to every economic question. Good news can be priced in; bad news can be less bad than expected. Test two separate targets: evidence-grounded economic interpretation, and subsequent market-relative return forecasting.

1. **Repair the interpretation graph first.** Require channel-specific evidence, especially for discount rates. Define materiality using a comparable numerical measure and distinguish prior issuer guidance from market consensus. Preserve unknowns, rumors and opposing channels.
2. **Use a date-selected sample.** Take roughly 100 consecutive announcements across several tech companies, including small, mixed and no-change cases. Freeze the sample rule, prompts, labels and baseline before looking at performance. Include indirect customer/supplier stories; this pilot only tested direct company news.
3. **Add expectations and timing.** Supply prior guidance or dated consensus that was available before the announcement. Record actual input receipt and inference completion. Evaluate returns beginning after the system could act, with one- and five-trading-day horizons and a market comparator. Do not credit the already-completed overnight move.
4. **Evaluate a held-out period and then collect prospectively.** Compare against keyword/numeric-surprise and no-news baselines. Test calibration, abstention coverage and errors, not just correct signs. A later chronological test reduces tuning bias; only future collection addresses the central concern that the model may already know historical outcomes.

If the goal is to predict a shock **several days before its announcement**, freeze inputs several days earlier and exclude the announcement itself. That is an anticipation experiment, different from this announcement-response test. Historical publication dates alone cannot establish that the collector had the information then.

## Reproducible artifacts

- [Frozen initial protocol and partial run](reports/historical-pilot/20261012T035446Z-6744bb8277/protocol.json).
- [Completed aggregate results and continuation protocol](reports/historical-pilot/20261012T040111Z-e88d11237e/summary.json).
- [Initial inputs](fixtures/historical-pilot-inputs.json) and [separate evaluation labels](fixtures/historical-pilot-labels.json).
- Each run contains case directories with exact requests, validated answers and stage evidence. The completed continuation also preserves parsed raw provider responses before validation.

Run another dry protocol with `python -m jev_news.historical_pilot`. Actual inference requires `--live` and a locally available `TYPESAFE_API_KEY`. Re-running would incur new calls and is not needed to inspect the saved pilot.
