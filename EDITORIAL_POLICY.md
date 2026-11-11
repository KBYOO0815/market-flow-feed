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

## 회차별 저장
공개 시 최신 morning-briefing.json과 briefings/YYYY-MM-DD.json의 해당 회차를 한 커밋으로 함께 저장한다. 날짜 파일의 editions 키는 07:30, 11:30, 15:30, 20:00이다. 이전 회차의 저장본은 유지하며, 동일 회차의 검증된 정정은 해당 키만 갱신한다. 발행 전 초안은 이 저장본에 넣지 않는다. 앱은 최초 공개 회차를 선택한 뒤 사용자의 선택을 새로고침 시에도 유지한다. 과거 회차는 당시 공개본이며 현재 시세로 해석하지 않는다. 기존 기록이 없는 회차를 다른 시각의 뉴스로 채우지 않는다.

## 회차 간 신규성·중복 차단 (필수)
- 같은 한국 거래일의 이전 모든 발행 회차(07:30/11:30/15:30/20:00)와 현재 공개 루트, 날짜별 briefings/YYYY-MM-DD.json을 먼저 읽고 사건 단위로 비교한다. 제목, URL, 출처, 표현이 달라도 같은 사건/동일 사실이면 새 회차에 다시 싣지 않는다.
- 예외는 이전 회차 이후 발생·발표된 실질적인 새로운 사실(새 공시, 수치 변경, 정책 결정, 시장 종가 확정, 추가 제재, 계약 변경 등)이 원문 시각과 HTTPS 출처로 검증된 경우뿐이다. 이때 summary는 새로운 사실만 명확히 적고 reviewNote에 이전 회차 사건 ID, 새 사실, 최초 발생·발표시각, 중복이 아닌 이유를 기록한다. 단순 분석·전망·제목 교체·시각 갱신은 예외가 아니다.
- 각 회차는 국외 최대 10건을 먼저, 국내 최대 10건을 다음에 배치한다. 20건은 최대치이지 목표치가 아니다. 부족한 건수를 채우기 위해 이전 회차 사건이나 오래된 기사를 복사하지 않는다. 검증된 신규 재료가 없으면 items=[]를 허용한다.
- 새 회차 작성 시 검색 범위는 직전 회차 이후의 신규 뉴스·공시·후속 업데이트이며, 해외 시장/정책/빅테크 발언과 국내 공시/정책/실적/수주를 모두 확인한다. 검증된 후보의 채택/제외 이유와 중복 판정을 작업 결과에 간단히 기록한다.
- 07:30/11:30/15:30/20:00은 각각 독립된 발행 시각이다. 회차별 파일에 과거 회차의 뉴스 또는 12:25 같은 비정규 시각의 복구 자료를 신규 뉴스로 재표기하지 않는다. 과거 자료 복구는 별도 archive로만 보존하고 명시적으로 구분한다.
- 발행 전 최종 검증에서 같은 날 기존 회차의 사건 ID 및 사건 내용과 비교하고, 새 사실을 증명하지 못하는 중복 항목은 제외한다. 실시간 시세/수급은 해당 시각의 관측 근거가 없으면 삭제한다.
