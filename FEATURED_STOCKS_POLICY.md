# Market Flow 특징주 — 단일 ChatGPT 예약 → GitHub JSON → 앱 (2026-11-17)

## 운영자 / 데이터 흐름
- **정규 발행 실행자:** ChatGPT 예약 작업 `Automation_19be7cd0af808191aecbcc421c15a01c` (기존 작업 유지·활성화). 독립 감시 `6afafb9de2288191a51add93c667ed60`은 누락/품질 결함 확인 및 허용된 복구만 수행하고 정규 회차를 새로 생성하지 않는다.
- 일정: `Asia/Seoul`, KRX 거래일 09:40 · 11:40 · 13:40 · 15:40 · 20:10. 월~금이라도 공식 KRX 비거래일에는 신규발행하지 않음.
- **단일 발행 경로:** ChatGPT 공개 시세 직접 조회 → 통합 Top100과 +4% 종목 확정 → **선정 종목 전부 종목별 뉴스·공시·산업 재료 검색 → 조사 완전성 및 테마 검증** → 앱용 JSON 1회 원자 커밋 → 원격 재조회 → 앱 공개 JSON 조회. 시세 우선발행/상승재료 추가발행의 2단계 방식 사용 금지.
- **GitHub Actions 특징주 수집/발행 비활성화:** `.github/workflows/collect-featured-stocks.yml`, `.github/workflows/publish-featured-stocks.yml`는 수동 호출 시 안내 메시지만 출력. 특징주 서버 수집 및 발행 스크립트는 역사적 백업으로 남기며 신규 발행 경로에 연결하지 않음. `requests/featured-collection.json`, `drafts/featured-stocks.json`에 신규 요청·초안을 쓰지 않음.
- 뉴스 브리핑 `market-briefing.json`과 `Market Flow 시장 재료 저장` 작업은 별개이며 변경 금지.

## 시세와 종목 선별
- `schemaVersion:3`, `turnoverBasis:"KRX_NXT"`, `universeSize:100`, `amountUnit:"KRW"`, `rateBasis:"KRX_PREVIOUS_CLOSE"`.
- KOSPI/KOSDAQ 개별기업 보통주/우선주만. ETF·ETN·SPAC·REIT·펀드·채권·워런트 등 제외. 코드·종목 유형은 상장 마스터와 공개 원문을 교차확인; Naver type=ST만으로 주식 여부를 단정하지 않음.
- 후보: KRX 거래대금 상위 100 + NXT 거래대금 상위 100의 종목코드 합집합. Naver 공개 순위 `https://stock.naver.com/api/domestic/market/stock/default?tradeType=KRX&marketType=ALL&orderType=priceTop&startIdx=0&pageSize=100` 및 `tradeType=NXT` 해당 URL. 같은 거래일 KRX·NXT 누적 거래대금을 검증하고 합산하며 각각의 원천·retrievedAt/observedAt을 보존. NXT 404, API 누락은 0원이 아님.
- 후보 일괄 실시간 시세 조회 예: `https://polling.finance.naver.com/api/realtime/domestic/stock/<comma-separated-codes>`. `integratedPriceInfo.accumulatedTradingValueRaw`, `accumulatedTradingValueRaw`, `overMarketPriceInfo.accumulatedTradingValueRaw` 등 원천 필드가 실제 어떤 시장 범위를 뜻하는지 교차확인. API는 비공식이며 매 회차 응답 구조와 관측일 검증 필수.
- **경계 증명:** K100(검증된 KRX 100위), N100(검증된 NXT 100위), T100(후보 통합 100위)에서 `T100 > K100 + N100`이면, 두 원천 Top100이 각 시장에서 완전하고 후보 합집합의 거래대금·상장 유형이 전부 검증되었을 때 합집합 밖의 종목이 Top100에 진입할 수 없음. 세 원 단위 정수와 계산·출처·기준시각을 `rankingProof`에 남김. 이 조건을 만족하지 못하거나 100위 동률·원천 범위 오류가 있으면 추가 후보 검증; 증명 실패하면 발행 보류. 무관한 저유동성 종목 상세조회 404는 경계 증명이 충분할 때 장애 이유가 아님.
- 상승률은 **KRX 전일 정규장 종가 대비**. NXT 현재가/장후 등락률과 혼합하지 않음. 가능한 KRX 실제 가격과 전일 정규장 종가를 확인하여 `changeRate = (price / previousRegularClose - 1) * 100` 계산하고 원문 표시율과 비교. 신규상장으로 기준가격 미확인이면 comparison.eligible=false, changeRate=null. 20:10 KRX 정규장 종가 및 NXT 당일 최종 누적 거래대금 각각 확인, 전일·당일 혼합 금지.
- Top100 중 비교 가능한 상승률 `>= 4.00`을 모두 선별. 같은 업종 상승 종목 복수는 실제 사업 연결·공통 재료 구분 후 themes, 기업 단독 이벤트는 individualStocks. 동일 종목 정확히 한 곳만. 테마 가중 상승률 = Σ(changeRate×integratedTradeAmount)/Σ(integratedTradeAmount), 포함된 +4% 종목에 한함. 별도 '최종 테마 판정' 표 금지.

## 상승 재료·테마 AI 자유 탐색 원칙 (2026-11-17 최종)

**목표:** 정해진 검색 체크리스트의 수행이 아니라, 선별된 모든 종목이 상승한 배경을 가능한 폭넓게 찾고 실제 근거로 설명한다. 시세·선별·스키마·게시 절차는 고정하되 **검색어, 검색 원천, 검색 순서, 검색 횟수, 테마 후보 탐색 방법은 AI가 자율 선택**한다. 이 조항은 이전의 종목별 의무 검색 원천 수/키워드 수/감사 건수/`sourceChecks` 4종 강제 지침보다 우선한다.

- **분석 시작점:** 통합 Top100의 +4% 이상 선정 종목 전체를 대상으로, 시장에서 동반 상승한 산업·사업·기술·정책·해외 재료 등 공통 촉매를 살피고 각 회사의 뉴스·공시·실적·수주·고객사·증권사 분석·기업 발표 등을 포괄적으로 탐색한다. 종목명에만 의존하거나 동일한 키워드를 반복하지 않는다. 실질 재료가 약하면 관점을 넓혀 검색한다. 특정 포털 또는 4개의 형식적 검색칸을 채우는 것은 완료 증거가 아니다.
- **테마 구분:** 단순 동일 업종은 테마의 충분조건이 아니다. 두 종목 이상에서 공통 산업 모멘텀·수혜 기대·구체 재료가 확인되면 테마로 묶을 수 있다. 단일 동일 기사가 반드시 필요하지는 않지만 확인된 공통 근거를 요약·링크한다. 서로 다른 단독 재료만 확인되면 개별 특징주로 둔다. 같은 종목은 정확히 한 곳에 포함한다. 테마 등락률은 포함된 선별 종목의 통합 거래대금 가중평균.
- **회차 간 근거:** 이번에 다시 선정된 종목에 대해 D~D-3 이전 회차의 `reason`/테마 이유·공개시각·원문을 참고한다. 유효한 관련 사실은 신규 재료가 없더라도 `prior_fact`로 유지할 수 있다. 실제 정정·취소·무관·기간 종료·오류면 제외 이유를 남긴다. 신규 사실은 신규로 표시하고, 오래된 자료를 당일 새 촉매로 가장하지 않는다.
- **근거 판단:** 실제 보도·공시·기업 발표·원문 보고서를 열람한 경우 그 HTTPS 출처 URL, 사실의 최초 발표시각, 확인 사실을 기록한다. 기사에서 상승 인과를 명시한 경우 `source_attributed`, 주가와 관련은 있지만 인과가 입증되지 않은 자료는 `related_fact_only`로 표기한다. 실제 첫 공개시각이 현재 `asOf`보다 늦으면 당시 상승 원인으로 소급하지 않는다. 원문 확인이 되지 않으면 사실을 만들어내지 않는다.
- **미확인 처리:** 검색 방법·회수는 자율적이지만 모든 선정 종목에 대해 실질적인 조사를 마쳐야 한다. 관련 근거를 찾지 못한 경우만 `reason:null`과 `unconfirmed`로 판정한다. 외부 원천 접근 실패·원문 미검증·시간 부족은 조사 미완료(`incomplete`)이며 없는 원인이라고 단정하거나 성공 발행하지 않는다.
- **최소 감사 및 발행 게이트:** `reasonResearchAudit`는 `selectedStockCodes`의 각 코드와 1:1 대응한다. 실제 종목별 조사시각·원천/검색어·확인한 자료 URL·조사 구간·완료/미완료·재료 분류를 정직하게 기록한다. 기존 필드 `code,status,checkedAt,searchedSources,searchQueries,checkedWindow,evidenceUrls,reasonClassification`을 보존하고 이전 근거의 유지·교체·제외 또는 원문 감사 기록은 실제 정보가 있을 때 선택적으로 남긴다. 4종 `sourceChecks`를 억지로 채우거나 모든 원천을 조회했다고 허위 표시하지 않는다. 시세·선정 누락·테마 중복·기존 근거 무단 소실·원문 없는 가짜 사실을 검증하고, 문제가 해결되지 않으면 성공 발행하지 않는다. 별도 중간 발행 없이 최종 JSON을 단 한 번 게시한다.

### 독립 감시와 역할 구분

- 기존 감시 작업 `6afafb9de2288191a51add93c667ed60`을 유지한다. 정규 작업은 **실제 분석과 최종 저장**, 감시는 **발행 여부·자료 품질·이전 근거 소실 여부를 사후 검증**한다. 정규 분석의 자유 탐색에 검색 소스 개수나 고정 단계 강제 규칙을 추가하지 않는다.
- 과거 회차를 복구할 때는 그 회차 시세 `asOf`와 기존 정상 사실을 보존하고, 당시 최초 공개된 자료만 검증 후 반영한다. 실제 조사하지 않은 과거 검색 이력을 소급 생성하지 않는다. GitHub 원자 저장·앱 v3 호환·원격 재조회 실패 시 원본 보존.

---
## 앱 호환 JSON 계약
기존 앱 `KBYOO0815/market-flow-app/src/featuredStocks.ts`의 `parseDailyFeaturedStocks` / `validateV3` 및 `src/FeaturedStocksScreen.tsx` 기준을 계속 충족할 것. 앱 코드를 변경하지 않고 JSON을 맞춘다.

- 공개 root: `KBYOO0815/market-flow-feed/featured-stocks.json`
- 공개 날짜별: `featured-stocks/YYYY-MM-DD.json` — `{"date":"YYYY-MM-DD","editions":{"09:40":{...},"11:40":{...}}}` 형태, 실제 발행된 슬롯만 기록.
- 공개 목록: `featured-stocks/index.json`. 최신 날짜가 위.
- 앱은 날짜별 공개 JSON 직접 조회. 현재 UI에 표시하는 날짜는 **D와 D-1**로 유지; 공개 서버에는 D~D-3 **4개 달력 날짜**를 보관한다. 앱의 조회 날짜와 서버의 보관 기간은 별개다.
- 공개 root는 최신 edition 필드를 최상위에 두고 `days`에 위 날짜별 사본을 최신순으로 포함한다. 과거 구버전 root 첫 전환 시 원본 SHA 백업을 보존한다.
- edition 필수: `schemaVersion,date,slot,releaseAt,asOf,collectionStartedAt,reviewedAt,publishedAt,turnoverBasis,universeSize,amountUnit,rateBasis,tradingDayEvidence,status,stocks,selectedStockCodes,themes,individualStocks,rankingProof`. `releaseAt`은 `YYYY-MM-DDTHH:mm:00+09:00` 형식의 **원래 회차**, 다른 시각은 모두 실제 관측·검증·작성시각.
- `tradingDayEvidence`: `date, verified:true, isTradingDay:true, sourceUrl, checkedAt, facts`.
- `status`: `{collection:"success",validation:"success",publication:"success"}`는 세 단계 실제 성공이 확인된 발행물에만 사용. GitHub 변경 실패 시 기존 발행물 보존하며 허위 상태를 만들지 않는다.
- `stocks`는 통합 거래대금 내림차순·동률 코드순 **정확히100개**. `code,name,turnoverRank,krxTradeAmount,nxtTradeAmount,integratedTradeAmount,changeRate,rateMarket:"KRX",price,previousRegularClose,comparison` 필드. 금액은 원 정수, 가격은 실제 원문. comparison은 `{eligible:true,basis:"KRX_PREVIOUS_REGULAR_CLOSE"}` 또는 비교불가 이유 명시. 앱은 계산수익률과 changeRate 차이 0.000002% 이내까지 검사한다. 없는 가격을 역산하여 채우지 않는다.
- `selectedStockCodes`는 실제 +4% 전체를 하락 아닌 순서로 정렬한 배열, `themes`와 `individualStocks`는 전부 중복 없이 분할. `themes`: `id,name,stockCodes,weightedChangeRate,integratedTradeAmount,reason`, 최소 2개 종목. 개별: `{code,reason}`. **기존 앱은 `reason:null`을 허용하지만 신규 운영 회차에서는 종목별 검색 완료 감사의 `unconfirmed` 판정이 있는 경우에만 허용**하며, 화면은 여전히 '당일 상승 이유 확인 안 됨'으로 표시한다.
- `reason`이 있다면 `summary,sourceUrl(HTTPS),publishedAt,checkedAt,causality(source_attributed|related_fact_only),verificationStatus:"confirmed",facts` 필수. publishedAt<=asOf<=checkedAt<=reviewedAt 실제시각 엄수. 새 사실이 미확인이면 reason=null.
- 현 앱의 필수 검사는 `src/featuredStocks.ts`의 현재 코드를 최우선한다. `reasonResearchAudit`는 **신규 운영상의 필수 추가 메타데이터**이나 기존 앱 파서에는 선택 필드이므로 기존 UI·앱 코드를 수정할 필요는 없다. 조사의 품질은 실제 원문과 사실 관계로 판정하며 검색 URL 수나 고정 검색 절차를 형식적으로 충족시키는 것으로 판단하지 않는다. 모의 JSON을 실거래 성공 데이터로 발행하지 않는다.

## GitHub 직접 커밋·중복발행 방지
1. 실제 KST 날짜·원래 예약 slot 및 거래일 증거 확정. 공개 시세/종목 유형 검증 후 +4% 대상 전 종목의 뉴스·공시·산업 자료 조사와 `reasonResearchAudit` 완료 여부를 검사. 원자료·분석·스키마·100위 경계값·+4% 누락·테마 가중률·시각 검증을 모두 마친 뒤 한 번의 발행 후보 작성.
2. **GitHub 연결 도구로** `main` HEAD와 현재 root/날짜별/index/보관기간 내 파일을 조회. 한 회차만 교체하고 다른 회차 보존; 더 최신 root가 있어도 과거 회차 보존 여부를 확인. 같은 날짜/slot의 후퇴 데이터 덮어쓰기 금지.
3. `D,D-1,D-2,D-3` 실제 성공 날짜만 보관, D-4 이전 날짜별 JSON 삭제. 하나의 Git Tree/Commit과 비강제 HEAD 이동으로 root·날짜별·index·삭제를 가능한 한 **원자적**으로 처리. 기존 충돌은 최신 HEAD를 다시 읽어 병합·재검증 후 제한 재시도. 여러 파일에 독립 `update_file`만 하고 원자 게시 성공이라 주장하지 않는다.
4. 작성한 커밋 기준으로 공개 root/날짜별/index/FIFO 삭제 내역 모두 재조회하여 완전히 같을 때만 공개 성공 보고. 비공개 `market-flow-app/data/featured-stocks.json` 미러는 앱의 실제 조회 경로가 아니므로 **선택적**; 갱신하지 않았다면 동기화되었다고 주장하지 않는다. 공개 파일만으로 앱이 동작함을 우선한다.
5. GitHub 권한 부재/원천 불완전/비원자적 저장/잘못된 시각/응답 구조 변경은 실패로 보고하고 구형 정상 JSON을 덮지 않는다. 조사·검증·발행 상태를 구분한다.
6. 작업이 20:10 이후 지연 실행되면 원래 slot 유지, 실제 관측시각 기록; 과거 시세가 없는 상태에서 과거 슬롯을 정상 실시간발행한 것으로 소급하지 않는다.

## 운영 점검
- 모의 스키마 검증 ≠ 실전 데이터 검증 ≠ GitHub 저장 성공 ≠ 앱에서 조회 성공.
- 최신 100위 컷오프(KRW/억원), +4% 종목 수, 테마·개별 수, sourceURLs, 실제 저장 commit SHA, 재조회 결과, 문제 원천을 짧게 보고.
- 앱 화면은 종래 **D/D-1 날짜·5회차 스와이프 UI**, 본문에 테마·개별 상승 재료. APK 빌드는 이번 데이터 발행 방식 전환 범위 밖이다.
- 원본 정책/과거 서버 스크립트는 Git history로 복구할 수 있다.
