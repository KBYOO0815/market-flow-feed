# Market Flow single-file protocol (2026-11-16)

The canonical public data is `market-briefing.json`, schemaVersion 1. ChatGPT's single scheduled task directly reads, researches, merges with the latest GitHub SHA, writes and verifies this file. No Actions publisher, draft, request, private mirror or daily JSON is involved. Existing historical feeds remain historical and are not fallback sources for the new app.

KST slots: 06:40, 08:40, 12:40, 19:40. On verified KRX closed days only 06:40 and 19:40 run. Preserve the scheduled slot despite delayed execution. Retain calendar D through D-3; no fabricated empty days. The app displays the same four calendar days. Feature-stock data is independent and remains on its existing feed.

## Storage and research are separate

`session.asOf` is the actual research cutoff, never a claim of complete coverage. `researchStatus` is complete/partial/failed. `researchAudit.domains.foreignNews`, `domesticNews`, `usThemes` each hold status, actual attemptedAt/checkedAt, windowStartExclusive/windowEndInclusive, completedThrough, failedSources, alternativeSources and pendingWindows. Only a verified contiguous complete interval advances completedThrough. The next run rechecks unresolved news windows independently. Carry pending ranges and completedThrough in top-level `researchState` before FIFO removes session content. Do not copy expired news into that state.

`usThemeStatus`: verified_themes, verified_no_theme, insufficient_data; non-06:40 is not_applicable. Empty themes with insufficient evidence do not mean no strong theme. Missing legacy audit fields mean unknown, not complete. Report stored/verified separately from source research.

## Reproducibility

Foreign/domestic news: each <=10, independent impactRank sequences, explicit region, HTTPS source, actual publication time, event/fact keys and candidate decisions. Existing baseline is not new delta. Preannounced schedules are not new events. A reputable report of discussion remains an attributed report, not a confirmed decision. Unverified publication time cannot establish newness.

06:40 evidence stays in the same JSON under researchAudit.usThemeEvidence: sessionDate, session/timezone, sourceUrls, observed/collected times, dollarVolumeDefinition, completeness, all 50 ranked rows (ticker, companyName, common/adr securityType, rank, dollarVolume in USD, regularChangePct, HTTPS sourceUrl, observedAt; after-hours values with separate sources and times if verified), exclusions and common catalyst sources. Actual turnover is required; closing price times total volume is not actual turnover. Every selected theme has `memberTickers` listing all calculation members, weightedChangePct, totalDollarVolume and up to five display stocks. At least two verified members, positive turnover-weighted change, same-day common catalyst; no invented ranking. Arithmetic correctness does not prove input correctness or universe completeness.

## Writer helper

Run locally within the research task (not a scheduled Actions publisher):

```
python3 scripts/market_briefing.py validate market-briefing.json
python3 scripts/market_briefing.py merge CURRENT.json DRAFT.json OUTPUT.json
```

DRAFT is `{date,isKrxTradingDay,session,researchState?}`. Fresh drafts require domain audit statuses. Old sessions are accepted structurally without silently certifying their research. Re-read remote JSON and SHA immediately before merging; retry conflicts by reading/remerging, never force-write. Re-read the exact saved file afterwards and compare. The helper checks structure, retention, timestamps, status consistency and arithmetic; it cannot certify article truth, KRX trading status, dollar-turnover methodology or coverage.

## APK 00.14

Reads the single public JSON once per refresh, shows four slots and four retained dates, preserves manual selection on refresh/restart, distinguishes closed-day slots, missing/future editions and research/US-theme uncertainty. Invalid/network responses retain the last good display with an error. No private credentials are bundled. The build/device workflows build and test APKs only; they are not news publishers. Model/reasoning choice is not asserted by app code.
