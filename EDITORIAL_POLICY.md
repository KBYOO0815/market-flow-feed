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

## 후보 수집 → 중요도 선별 → 발행 파이프라인 (필수)
- 각 회차의 준비 시각에 국내외 여러 신뢰 가능한 원문 출처(Reuters/AP/공식 IR/SEC/Fed/백악관, KRX/KIND/DART/정부·거래소/주요 언론)를 병렬 탐색하고, 직전 회차 마감 이후부터 실제 조사 시각까지 새로 발표되거나 실질적으로 수정된 모든 관련 후보를 수집한다. 한두 개 검색 결과나 이전 브리핑을 수집 풀로 대체하지 않는다.
- 검색은 국외(미국 지수·금리·Fed·정책/트럼프·빅테크 발언·반도체/AI·신용/데이터센터·중국·원자재·지정학)와 국내(시장·수급·DART/KIND·정부·실적·수주·증자·지분·자사주·산업)를 각각 독립 수행한다. 충분한 후보가 있는 경우 국내외 각각 최소 20개 이상을 먼저 검토하도록 노력하되, 실제 없는 후보나 출처를 만들어 수를 맞추지 않는다.
- 후보별로 사건 고유 식별자, 원문 URL, 최초 보도/공시 시각, 신규 사실, 관련 국내 업종/종목, 확정성, 국내 주식시장 파급 범위와 강도, 이전 회차 중복 여부를 기록한다. 원문을 열어 시간·수치·사실을 검증하지 못한 후보는 제외한다.
- 같은 사건을 다룬 복수 기사는 하나로 병합하고, 이전 회차의 동일 사실은 제거한다. 단순히 다시 보도되거나 시장 영향 해설만 추가된 경우 신규 재료로 보지 않는다. 실질적 후속 사실은 변화량과 발표시각을 명시할 때만 허용한다.
- 중요도는 ① 국내 시장 전체 영향 ② 여러 업종 영향 ③ 개별 업종 영향 ④ 개별 종목 영향 순으로, 사실의 확정성·새로움·경제적 규모·전파 가능성을 함께 평가한다. 검증된 후보를 국내외 별도로 순위화하고 각각 상위 최대 10건만 최종 발행한다. 최종 JSON은 국외 먼저 국내 다음, impactRank 연속 부여.
- 작업 결과에 후보 수/검증 통과 수/중복 제외 수/최종 국외·국내 발행 수를 실제 집계로 보고한다. 수치를 셀 수 없다면 '미집계'로 보고한다.
- 후보 수집은 스크래핑 가능한 공개 원문과 공식 API/공시를 우선하며 로그인 우회, 접근제한 회피, 기사 전문 무단 재배포를 하지 않는다. 최종 JSON은 원문 링크와 독자적으로 요약한 짧은 재료만 담는다.

## 최근 5일 FIFO 보관
- 공개 briefings/YYYY-MM-DD.json에는 각 날짜의 07:30/11:30/15:30/20:00 회차를 독립 보존한다. 새 회차 발행 시 KST 발행일 D부터 D-4까지 **5개 달력 날짜**의 날짜별 파일만 유지하고 D-5 이전 날짜별 파일은 같은 발행 커밋에서 제거한다. 휴장일도 달력상 날짜 계산에 포함하며 보관 날짜에 거래가 없으면 파일을 생성하지 않는다.
- 최신 morning-briefing.json은 최신 회차 조회용이며 날짜별 FIFO의 추가 날짜로 세지 않는다. briefings/recovered/는 복구 증빙 자료이므로 일반 날짜별 FIFO 대상과 구분한다.
- 과거 날짜 삭제는 실제 새 회차가 검증되어 발행되는 시점에만 실행한다. 초안 작성 중에는 보관본을 삭제하지 않는다. 사용자 앱은 최근 5일 중 존재하는 날짜·회차를 조회하고 선택할 수 있어야 한다. 앱의 날짜별 탐색 UI/조회 로직이 별도로 지원되는지도 확인해야 한다.

## 발행 차단형 검색 감사 (2026-11-12 11:30 회차부터 필수)
- 신규 브리핑 JSON에 researchAudit를 반드시 추가한다. 누락되면 발행 검증이 실패한다.
- researchAudit.coverage에는 foreign_market(미국 증시/금리/환율), foreign_policy(Fed/정책/지정학), foreign_technology(엔비디아/반도체/AI/빅테크), domestic_disclosures(DART/KIND 공시/실적/수주), domestic_policy(정부/금융규제), domestic_market(KRX 시장/수급/옵션만기) 6개 키를 모두 채운다. 각 값은 checkedAt(실제 조사시각, asOf 전 30분 이내)과 sourceUrls(실제로 조사한 HTTPS 원문/공식 목록 URL 배열)이다.
- researchAudit.foreignCandidates, domesticCandidates, verifiedCandidates, duplicateExcluded는 실제로 확인한 0 이상의 정수로 작성한다. '검색했다'는 말만으로 기록을 대신하거나 확인하지 않은 URL·시각·건수를 꾸며서는 안 된다. 6개 분야를 확인하지 못했다면 그 회차 발행을 중단하고 미완료 이유를 보고한다.
- 시장 충격 사건의 최종 점검을 별도 실시한다. 한국 장전 07:30에는 미국 정규장 종가와 미국 장마감 후 신규 속보, 국내 06:00~07:30 공시·개장 전 주요 뉴스를 반드시 재검색한다. 특히 엔비디아/삼성전자/SK하이닉스/금리/정책·규제/시장 급변과 주요 국내 공시를 확인하고 중요도를 다시 평가한다.
- 원문 발행시각이 발행 목표 이후인 재료는 그 회차에 절대 넣지 않는다. 기존 07:30 회차의 누락을 나중에 발견하면 당시 시각을 소급 조작하지 말고 다음 회차의 새 사실 여부를 판정하거나 누락 사유를 별도로 보고한다.

## 2026-11-12 시행: 7회차 시간표 및 3일 보관 (기존 시간표·5일 규정보다 우선)
- 한국 거래일 KST 준비→발행: 06:30→06:40, 07:30→07:40, 11:40→11:50, 14:40→14:50, 15:40→15:50, 18:40→18:50, 20:10→20:20. 7개 회차만 유효하며 구 회차 07:30/11:30/15:30/20:00은 신규 발행하지 않는다.
- 매 회차 시작 직전 기준 새 뉴스·공시를 수집·검증하고 10분 후 공개한다. 06:40 회차는 미국 장 마감/시간외, 07:40 회차는 06:40 이후 신규 공시·뉴스를 우선한다. 14:50/15:50 회차는 해당 관측시각과 장 마감 여부를 구분한다.
- 기존 회차 기록은 역사적 자료로만 남긴다. 신규 발행 회차와 날짜별 editions 키는 새 7개 시간으로 작성한다.
- 서버 날짜별 보관은 발행일 D, D-1, D-2의 **3개 달력 날짜**만 유지한다. 발행 커밋에서 D-3 이전 briefings/YYYY-MM-DD.json 삭제. 복구용 별도 자료는 기존과 같이 일반 날짜별 파일과 구분한다.
- 앱 UI 및 APK는 변경하지 않는다. 기존 앱이 새 7개 회차 키를 정상 표시하는지 별도 호환성 검증이 필요하며, 검증 전에는 정상 표시를 보장하지 않는다.

## 2026-11-12 추가 회차 (최신 우선)
- 기존 7회차에 **08:40 검색·준비 → 08:50 발행 (KST)** 추가. 전체 8회차는 06:40, 07:40, 08:50, 11:50, 14:50, 15:50, 18:50, 20:20. 준비는 각각 10분 전. 기존 검색·검증·중복 제거 규칙과 D~D-2 보관 유지.

## 사실만 발행 (최우선 편집 원칙)
- 검색 후보를 수집할 때와 최종 발행할 때 **의견, 전망, 추측, 해석, 평가, 추천, 목표주가, 투자 판단**을 뉴스 사실로 기술하지 않는다. 기자·증권사·전문가·기업 관계자의 의견을 인용했더라도 그 의견 내용 자체는 재료로 채택하지 않는다.
- 채택 가능한 것은 확인 가능한 **발생 사실**(공식 발표, 공시, 확정 실적·계약·금액, 실제 거래·시세, 정책 결정, 실제 발언이 있었다는 사실)뿐이다. '발언했다'는 사실과 그 발언 내용이 사실로 입증되었다는 것은 구별한다. 소문·익명 주장·미확인 보도는 확정 사실로 서술하지 않는다.
- 제목과 summary에는 검증된 주체·행위·일시·수치·출처만 담는다. '호재/악재', '수혜', '우려 확대', '상승 기대', '가능성 높음', '주가 영향 예상', '시장에 긍정적' 등 주관적 평가·예측 문장을 금지한다.
- 관련 종목은 객관적 계약·공급·지분·사업 관계가 확인될 때만 연결한다. 단순 테마 추정으로 관련 종목을 덧붙이지 않는다.
- 중요도 순위는 내부 기사 배열 기준으로만 사용하며 중요도에 대한 의견·투자 해석을 기사 본문에 노출하지 않는다. 사실을 검증할 수 없으면 제외하고 부족한 건수는 그대로 둔다.
- 최종 발행 직전에 각 제목과 summary를 사실/의견으로 문장 단위 재검토하여 의견 문장이 하나라도 있으면 삭제하거나 확인된 사실만으로 재작성한다. 임의 수치·시각·근거 생성 금지.

## 발행 스키마 분류 강제 (2026-11-12 오류 재발 방지)
- 기사 `category` 값은 서버 허용 목록 **미국증시, 반도체·AI, 정책·발언, 국내공시, 기타** 중 하나만 사용한다. `실적`, `계약`, `금융`, `산업` 등은 기사 내용 설명에는 쓸 수 있어도 category 값으로 넣지 않는다. 기업 실적·계약 공시는 `국내공시`로 분류한다.
- 초안 저장 전에 `python3 scripts/prepare_feed.py --stage <초안파일> <검증출력파일>`로 스키마 전체를 검증한다. 검증 실패 시 발행용 초안을 덮어쓰지 말고 원인을 수정한 후 재검증한다.
- 자동 발행 성공은 실제 공개 `morning-briefing.json`의 `releaseAt`과 `briefings/YYYY-MM-DD.json` 회차를 재조회하여 확인한다. 초안 생성만으로 성공이라고 보고하지 않는다.

## 검색 누락 방지·후보별 탈락 사유 기록 (최우선)
- 국내 DART/KIND 기업공시(실적·계약·자사주·증자·투자), 정부·국회·금융위·산업부, 연합뉴스·로이터를 **각각 독립적으로** 검색한다. 한두 개 시장종합 기사 URL을 여러 검색영역의 검증 증거로 재사용하는 것으로 해당 영역 탐색을 완료했다고 간주하지 않는다.
- 회차별 전회차 이후 발표된 기업 실적·공급계약도 반드시 후보에 포함한다. 뉴스 매체가 아닌 공시 원문 우선; 공시 접근이 어려우면 신뢰할 만한 기사 원문으로 교차 검증한다.
- 모든 후보에 대해 `선정/중복/시간범위 밖/의견·전망/원문 확인 불가/중요도 10건 제한/기타` 중 **정확한 판정 및 사유**를 조사 기록에 남긴다. 탈락 사유가 없는 후보는 검증 완료로 계산하지 않는다. 검증 후보가 1건뿐인데 검색 후보가 다수인 경우 모든 탈락 사유를 다시 점검한다.
- 발행 전 국외 최대 10건·국내 최대 10건의 **각 영역별 후보 목록**을 독립 검토한다. 10건을 맞추기 위해 임의 사실을 만들지 않되, 국내외 주요 신규 공시·발표를 1건만 남기고 누락하는 일이 없도록 한다.
- 단순히 researchAudit.coverage의 6개 URL 칸을 채운 것만으로 검색 품질을 통과했다고 보고하지 않는다. 실제 검색 결과와 후보별 판단이 있어야 한다.
- 지난 회차의 누락을 발견하면 원문·시각을 확인하여 다음 발행에서 `이전 회차 이후 확인된 미반영 사실`로 다루되, 과거 asOf·reviewedAt을 조작하거나 과거 시각에 실시간 발행한 것으로 표시하지 않는다.
