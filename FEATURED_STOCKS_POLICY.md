# Market Flow 특징주 — 데이터 계약 및 GitHub 발행 규칙

> 이 문서는 **앱과 GitHub JSON 사이의 데이터 형식·저장 규칙만** 정의한다. 종목별 뉴스 검색어, 검색 원천·횟수·순서, 테마 탐색·상승 이유 분석 방법은 **ChatGPT 특징주 정규 예약 작업**이 자율적으로 결정한다. 이 문서를 AI 뉴스 분석 지침으로 사용하지 않는다.

## 운영 구조

- **정규 발행:** ChatGPT 예약 `Automation_19be7cd0af808191aecbcc421c15a01c` → JSON 생성 → GitHub 공개 저장소 `KBYOO0815/market-flow-feed`에 직접 발행 → 앱 조회.
- **독립 감시:** `6afafb9de2288191a51add93c667ed60`은 발행·품질 이상을 점검하며 정규 발행을 중복하지 않는다.
- **예약 시간:** Asia/Seoul, KRX 거래일 09:40·11:40·13:40·15:40·20:10. 휴장일에는 신규 발행하지 않는다.
- 뉴스 브리핑 `market-briefing.json` 및 기존 앱·브리핑 예약 작업은 이 데이터 계약의 변경 대상이 아니다. 퇴역한 GitHub Actions·서버 스크립트는 특징주 정규 발행에 사용하지 않는다.

## 시세·선정 데이터 규격

- `schemaVersion: 3`, `turnoverBasis: "KRX_NXT"`, `universeSize: 100`, `amountUnit: "KRW"`, `rateBasis: "KRX_PREVIOUS_CLOSE"`.
- 대상은 KOSPI·KOSDAQ의 개별기업 보통주/우선주이며 ETF·ETN·SPAC·리츠·펀드·채권 등은 제외한다.
- KRX 거래대금 상위 100과 NXT 거래대금 상위 100의 종목코드 합집합에서 **같은 거래일의 KRX+NXT 누적 거래대금**으로 진짜 통합 Top100을 산정한다. 원천 미조회·404를 0원으로 간주하지 않는다.
- 통합 Top100 완전성은 KRX 100위 `K100`, NXT 100위 `N100`, 후보 통합 100위 `T100`에 대해 **`T100 > K100 + N100`** 및 원천 완전성을 검증하거나 동등한 근거를 `rankingProof`에 기록한다. 검증 불가 시 정상 발행하지 않는다.
- **등락률은 KRX 전일 정규장 종가 대비 KRX 가격**으로 계산한다: `changeRate = (price / previousRegularClose - 1) * 100`. 20:10 회차에서도 등락률 산정 가격은 당일 **KRX 정규장 종가**이며, NXT 장후 가격과 혼합하지 않는다. NXT 거래대금은 당일 장후 최종 누적값을 반영한다. 가격과 시세 원천의 날짜·시장·기준을 검증한다.
- 통합 Top100 중 비교 가능한 `changeRate >= 4.00` 종목을 **모두** `selectedStockCodes`에 담는다. 기준가격이 없으면 임의 역산하지 않고 비교 불가를 명시한다. 테마는 최소 2종목이고 개별 종목과 중복되지 않는다. 테마 가중 등락률은 포함된 선정 종목의 통합 거래대금 가중평균이다.

## 앱 호환 JSON 계약

기존 앱 `KBYOO0815/market-flow-app/src/featuredStocks.ts`의 `validateV3`와 화면의 현행 호환성을 유지한다.

| 공개 경로 | 계약 |
|---|---|
| `featured-stocks.json` | 최신 성공 edition의 필드를 최상위에 두고 `days`에 보관 날짜별 데이터를 최신순 포함 |
| `featured-stocks/YYYY-MM-DD.json` | `{"date":"YYYY-MM-DD","editions":{"09:40":{...}, "11:40":{...}}}`처럼 실제 발행된 회차만 포함 |
| `featured-stocks/index.json` | `schemaVersion:3` 및 최신순 `dates:[{date,path}]` 등 앱 조회에 필요한 목록 |

- **보관:** 서버는 D~D-3의 4개 *달력 날짜*만 유지하고, 앱에는 D·D-1을 표시한다. 없는 회차·날짜를 성공 데이터로 생성하지 않는다.
- **edition 필수 키:** `schemaVersion,date,slot,releaseAt,asOf,collectionStartedAt,reviewedAt,publishedAt,turnoverBasis,universeSize,amountUnit,rateBasis,tradingDayEvidence,status,stocks,selectedStockCodes,themes,individualStocks,rankingProof`. 시각은 실제 ISO8601/KST offset을 사용한다. `releaseAt`은 원래 예정 회차시각이다.
- **`stocks`:** 통합 거래대금 내림차순·동률 코드순 정확히 100개. 각 종목에 `code,name,turnoverRank,krxTradeAmount,nxtTradeAmount,integratedTradeAmount,changeRate,rateMarket,price,previousRegularClose,comparison` 기록. 금액은 원 단위 정수, `rateMarket:"KRX"`; 비교불가 사유는 `comparison`에 명시한다.
- **분류:** `selectedStockCodes`의 모든 종목은 `themes[]` 또는 `individualStocks[]`에 정확히 한 번만 들어간다. `themes[]` 원소는 `id,name,stockCodes,weightedChangeRate,integratedTradeAmount,reason`, `individualStocks[]` 원소는 `code,reason`을 사용한다.
- **`reason`:** 확인된 관련 자료가 있으면 `summary,sourceUrl,publishedAt,checkedAt,causality,verificationStatus,facts`를 기록한다. `sourceUrl`은 실제 HTTPS 근거, `causality`는 `source_attributed` 또는 `related_fact_only`, `verificationStatus:"confirmed"`. `publishedAt <= asOf <= checkedAt <= reviewedAt`을 지킨다. 확인되지 않은 사유는 앱에서 허용하는 `reason:null`을 사용하되 원문 없이 사실을 만들어내지 않는다.
- **보조 메타:** `reasonResearchAudit` 등은 예약 작업이 실제 수행한 확인 사항을 기록하는 추가 필드이며 앱 필수 계약을 변경하지 않는다. 이 문서는 **감사 로그 개수·뉴스 검색 방법을 강제하지 않는다**.
- **`status`:** `collection,validation,publication:"success"`는 각 단계가 실제 성공한 경우에만 기록한다. 모의값·미검증값을 성공으로 표시하지 않는다.

## GitHub 발행·보존 규칙

1. 정규 예약 작업은 시세·분석·앱 v3 형식 검증을 완료한 **최종 JSON만 한 회차에 한 번** 발행한다. 분석을 위한 중간 임시 JSON 선발행은 하지 않는다.
2. GitHub `main` 최신 HEAD의 root·날짜별·index·보관 파일을 읽고 동일 날짜의 다른 회차와 이전 성공 데이터를 보존·병합한다. 기존 정상 회차를 오래된 값으로 덮어쓰지 않는다.
3. 가능하면 Git Tree/Commit 및 비강제 HEAD 이동을 이용해 root·날짜별·index·FIFO 삭제를 **하나의 원자적 커밋**에 반영한다. 충돌 시 최신 HEAD 재조회·안전 재병합 후 제한 재시도한다. 독립 파일 수정 3회를 단일 원자 발행이라 주장하지 않는다.
4. **원격 재조회 검증:** 저장 커밋 기준 root·날짜별·index와 D~D-3 보관/삭제 내역이 일치한 뒤에만 발행 성공으로 보고한다. 실패 시 기존 정상 JSON을 보존하고 오류를 명시한다.
5. 앱이 실제 조회하는 공개 날짜별 JSON을 우선한다. 비공개 앱 저장소의 미러 파일은 선택 사항이며 갱신하지 않았다면 동기화했다고 보고하지 않는다.

---
이 문서는 **데이터 계약**이다. **AI의 뉴스 검색·상승 재료 판단·테마 분석은 정규 예약 작업의 프롬프트가 전담**한다.
