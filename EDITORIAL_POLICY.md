# Market Flow editorial refresh and publication policy

Publication slots: 07:30, 11:30, 15:30, 20:00 Asia/Seoul, only on verified KOSPI trading days.
Research preparation starts at 07:20, 11:20, 15:20 and 19:50 respectively. A scheduler may start a run a few minutes early: begin that edition's actual research immediately within its allowed 20-minute preparation window. Never end the run assuming another preparation run will happen later. Publication is handled by the public data repository workflow and may be delayed if execution or research is late.

## Rebuild the briefing from current evidence
- Read the previous public briefing, but never copy its summaries forward without a new review.
- Search new disclosures and news since the previous cutoff. Recheck every retained event against current sources and follow-up reports.
- Check source-page date, observation time and event time separately. Discard search snippets whose page is for a different day or whose timestamp cannot be verified.
- For index levels, individual stock direction, prices, percentages and flows, obtain a fresh timestamped observation. An opening-session decline is not a valid description of an 11:30 or afternoon market that has reversed.
- Remove superseded, contradicted, expired or unverifiable items. Do not replace them with guessed prices. Do not merely change asOf/reviewedAt on the old text.
- Persistent factual events may remain only after checking that they are still active; record the actual current-review URL, review time and reason in reviewNote.
- The 15:30 edition must not describe a pre-close observation as a confirmed closing price. If the final close is unavailable, omit the number or clearly use a fresh timestamped pre-close snapshot. Recheck confirmed closing figures for 20:00.
- Separate facts from interpretation. Exclude rumours and unverified figures. Include domestic disclosures/policy/earnings/orders/capital changes as well as international markets/Fed/policy/big-tech statements/AI-credit/China/geopolitics.
- Deduplicate events. Rank market-wide impact before multi-sector, sector and company impact. At most 10 foreign events first, then at most 10 domestic events; fewer verified items is acceptable.

## Required draft JSON
Top-level: schemaVersion=2, asOf (actual research cutoff with timezone), releaseAt (intended slot with timezone), tradingDayVerified=true, calendarSourceUrl (actual evidence for a KOSPI trading day), items.
Each item: id, title, summary, publishedAt (original source publication time), sourceUrl (HTTPS), sourceName, relatedStocks array, impactRank (continuous from 1), category (미국증시/반도체·AI/정책·발언/국내공시/기타), region (foreign/domestic), kind (news/market_snapshot), reviewedAt (actual review time), reviewSourceUrl (HTTPS current evidence), reviewNote (what was checked and why this still belongs), validUntil.
Every reviewedAt must be within 15 minutes before asOf. Do not invent timestamps.
News expires no later than the next scheduled slot. Intraday snapshots also require observedAt within 10 minutes before asOf and must expire within 15 minutes of observedAt. A snapshot that would expire before publication must be omitted.
asOf must be within 20 minutes before to 30 minutes after the intended release. A missed slot older than 30 minutes must be reported as missed; do not relabel old research as fresh.

## Stage, validate, then publish
1. Read the latest policy and current files from GitHub. Confirm the intended release slot from the scheduled preparation run, even if execution starts late.
2. Create/update identical reviewed drafts at private KBYOO0815/market-flow-app data/drafts/morning-briefing.json and public KBYOO0815/market-flow-feed drafts/morning-briefing.json. Use fresh file SHAs. Never expose the private source repository.
3. Validate with scripts/prepare_feed.py --stage when a shell is available; GitHub's publication workflow repeats validation independently.
4. Do NOT directly overwrite the public morning-briefing.json from a research run. The publisher waits for releaseAt, rejects stale drafts, drops expired snapshots, checks the current file SHA, refuses rollback, writes and reads back the actual public file.
5. A staged draft is not a successful publication. Verify the workflow result and public file releaseAt/asOf before reporting published. If the run ends before release, report staged/waiting honestly.
6. After a verified public publication, mirror that exact JSON to the private data/morning-briefing.json. At the next run, reconcile the latest public file first if a previous run ended while waiting.
7. On a KRX holiday, unverifiable market calendar, tool failure or missing evidence, do not fabricate a briefing or mark publication successful. Report the exact issue.
