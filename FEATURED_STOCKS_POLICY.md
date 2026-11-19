# Market Flow 특징주 — 데이터 계약 및 GitHub 발행 규칙

> 이 문서는 **앱과 GitHub JSON 사이의 데이터 형식·저장 규칙만** 정의한다. 종목별 뉴스 검색어, 검색 원천·횟수·순서, 테마 탐색·상승 이유 분석 방법은 **ChatGPT 특징주 정규 예약 작업**이 자율적으로 결정한다. 이 문서를 AI 뉴스 분석 지침으로 사용하지 않는다.

## 운영 구조

- **정규 발행:** ChatGPT 예약 `Automation_19be7cd0af808191aecbcc421c15a01c` → JSON 생성 → GitHub 공개 저장소 `KBYOO0815/market-flow-feed`에 직접 발행 → 앱 조회.
- **독립 감시:** `6afafb9de2288191a51add93c667ed60`은 발행·품질 이상을 점검하며 정규 발행을 중복하지 않는다.
- **예약 시간:** Asia/Seoul, KRX 주식시장 거래일 08:40·09:40·11:40·13:40·15:40·20:10. 해당 세션이 실제로 운영되지 않거나 유효한 체결가격을 확인하지 못하면 그 회차는 미발행한다. 20:10은 애프터마켓(통상 20:00 종료) 최종 유효 체결가를 사후 확정·발행하는 회차다. 수능일 등 특별 거래시간은 공식 공지에 따라 판정한다.
- 뉴스 브리핑 `market-briefing.json` 및 기존 앱·브리핑 예약 작업은 이 데이터 계약의 변경 대상이 아니다. 퇴역한 GitHub Actions·서버 스크립트는 특징주 정규 발행에 사용하지 않는다.

## 시세·선정 데이터 규격

- 기본 계약은 `schemaVersion: 3`, `turnoverBasis: "KRX_NXT"`, `universeSize: 100`, `amountUnit: "KRW"`, `rateBasis: "KRX_PREVIOUS_CLOSE"`다. `rateBasis`는 **분모가 KRX 전 거래일 정규장 종가**라는 뜻으로, 분자의 실제 거래시장·세션은 별도 `priceMarket`·`priceSession`으로 증명한다. 단, 현행 앱 TypeScript 타입은 `rateMarket:"KRX"`를 명시하나 **JSON v3 런타임 검증은 이 값을 직접 검사하지 않는다**. NXT 시장 값을 KRX로 거짓 표기해서는 안 되며, v3 소비자의 실제 로딩 동작을 확인해 호환성을 판정한다.
- 대상은 KOSPI·KOSDAQ의 개별기업 보통주/우선주이며 ETF·ETN·SPAC·리츠·펀드·채권 등은 제외한다.
- KRX 거래대금 상위 100과 NXT 거래대금 상위 100의 종목코드 합집합에서 **같은 거래일의 KRX+NXT 누적 거래대금**으로 진짜 통합 Top100을 산정한다. 원천 미조회·404를 0원으로 간주하지 않는다.
- 통합 Top100 완전성은 KRX 100위 `K100`, NXT 100위 `N100`, 후보 통합 100위 `T100`에 대해 **`T100 > K100 + N100`** 및 원천 완전성을 검증하거나 동등한 근거를 `rankingProof`에 기록한다. 검증 불가 시 정상 발행하지 않는다.
- **회차별 상승률:** `changeRate = (price / previousRegularClose - 1) * 100`에서 분모는 언제나 KRX 전 거래일 정규장 종가다. 분자는 08:40=NXT 프리마켓, 09:40·11:40·13:40=KRX 정규장, 15:40=KRX 정규장 당일 종가(특별 거래시간으로 아직 장중이면 당시 정규장 체결가), 20:10=당일 애프터마켓(KRX·NXT)의 시장·시각이 검증된 최종 유효 체결가를 사용한다. 20:10 시각에 거래 중이었다고 표시하지 않는다. 전일 기준가·분자 가격·체결시장·세션·시각·거래일·거래대금 원천을 확인한다.
- **세션 간 가격 검증:** 같은 거래일 15:40·20:10 회차의 당일 `price`는 달라도 정상이다(정규장·애프터마켓 별도 거래). 공통 종목의 `previousRegularClose`는 같아야 한다. 각 종목의 상승률 산식을 검증하고, 프리·애프터마켓 종목은 실제 가격 출처(edition의 `priceSession`, 종목의 `priceMarket`, `priceObservedAt`, `priceSourceUrl`)를 남긴다. 구형 `scripts/check_featured_close.py`의 '20:10=15:40 가격 일치' 검사는 변경된 기준에 맞춰 갱신한다. GitHub Actions 검사는 **발행 후 읽기 전용**이며 직접 커밋을 차단하거나 상승 이유를 재판정하지 않는다.
- 통합 Top100 중 비교 가능한 `changeRate >= 4.00` 종목을 **모두** `selectedStockCodes`에 담는다. 기준가격이 없으면 임의 역산하지 않고 비교 불가를 명시한다. 테마는 최소 2종목이고 개별 종목과 중복되지 않는다. 테마 가중 등락률은 포함된 선정 종목의 통합 거래대금 가중평균이다.

## 앱 호환 JSON 계약

기존 앱 `KBYOO0815/market-flow-app/src/featuredStocks.ts`의 `validateV3` 및 화면을 변경하지 않는다는 제약이 있다. 현재 앱의 `FEATURED_SLOTS`에 **08:40이 없어 해당 회차를 날짜별 JSON에 추가하면 전체 날짜 파일이 거부된다**. `rateMarket`은 TypeScript 타입에서 KRX 고정이나, 실제 JSON v3 런타임 검증은 이를 검사하지 않으므로 NXT 가격 회차의 로딩 가능 여부는 별도로 검증한다. 프리·애프터마켓 가격을 KRX로 허위 표기하지 않는다. 발행 전 앱의 실제 파싱·표시 호환성을 확인하고 미호환이면 해당 회차를 발행 보류·명시 보고한다. 앱 업데이트가 승인되면 `08:40`과 `priceMarket`·`priceSession`을 검증하도록 앱 데이터 어댑터를 개편해야 정상 서비스가 가능하다.

| 공개 경로 | 계약 |
|---|---|
| `featured-stocks.json` | 최신 성공 edition의 필드를 최상위에 두고 `days`에 보관 날짜별 데이터를 최신순 포함 |
| `featured-stocks/YYYY-MM-DD.json` | `{"date":"YYYY-MM-DD","editions":{"09:40":{...}, "11:40":{...}}}`처럼 실제 발행된 회차만 포함 |
| `featured-stocks/index.json` | `schemaVersion:3` 및 최신순 `dates:[{date,path}]` 등 앱 조회에 필요한 목록 |

- **보관:** 서버는 D~D-3의 4개 *달력 날짜*만 유지하고, 앱에는 D·D-1을 표시한다. 없는 회차·날짜를 성공 데이터로 생성하지 않는다.
- **edition 필수 키:** `schemaVersion,date,slot,releaseAt,asOf,collectionStartedAt,reviewedAt,publishedAt,turnoverBasis,universeSize,amountUnit,rateBasis,tradingDayEvidence,status,stocks,selectedStockCodes,themes,individualStocks,rankingProof`. 시각은 실제 ISO8601/KST offset을 사용한다. `releaseAt`은 원래 예정 회차시각이다.
- **`stocks`:** 통합 거래대금 내림차순·동률 코드순 최대 100개를 실제 원천으로 검증한다(현행 앱은 정확히 100개 요구). 각 종목에 `code,name,turnoverRank,krxTradeAmount,nxtTradeAmount,integratedTradeAmount,changeRate,rateMarket,price,previousRegularClose,comparison`을 기록한다. 가격 출처가 KRX 아닌 경우 실제 시장을 `rateMarket`·`priceMarket`에 정확히 적고, `priceSession`, `priceObservedAt`과 근거 출처도 기록한다. **앱이 수용할 수 없는 상태거나 실제 거래 종목이 100개 미만이면 완전한 Top100을 꾸며내지 않고 발행 보류한다.** 금액은 원 단위 정수이며 비교불가 사유는 `comparison`에 명시한다.
- **분류:** `selectedStockCodes`의 모든 종목은 `themes[]` 또는 `individualStocks[]`에 정확히 한 번만 들어간다. `themes[]` 원소는 `id,name,stockCodes,weightedChangeRate,integratedTradeAmount,reason`, `individualStocks[]` 원소는 `code,reason`을 사용한다.
- **`reason`:** 실제 관련 자료를 확인하면 `summary,sourceUrl,publishedAt,checkedAt,causality,verificationStatus,facts`를 기록한다. `sourceUrl`은 실제 HTTPS 근거, `causality`는 `source_attributed`(원인 직접 언급) 또는 `related_fact_only`(관련 사실을 바탕으로 한 **상승 배경 추정 포함**)를 사용한다. `verificationStatus:"confirmed"`는 **출처·사실의 확인**을 뜻하며 추정한 인과관계가 증명됐다는 뜻은 아니다. 추정은 `summary`에 추정·가능성으로 구별한다. `reason.publishedAt <= reason.checkedAt <= edition.reviewedAt`을 지킨다. 이전 회차에서 확인한 **동일한 근거**를 다음 회차에서 다시 사용하는 경우에는 실제로 확인한 `checkedAt`을 보존한다. `reason.checkedAt`이 새 회차의 `asOf`보다 이전이라는 이유만으로 오류로 처리하지 않는다. 재확인하지 않았다면 `checkedAt`을 현재시각으로 갱신하지 않으며, 재확인했다면 실제 확인한 시각으로 기록한다. 모든 회차에서 확인 가능한 새 재료를 독립 탐색하고, 원문의 유효성과 시장 상황을 평가한다. 확인 가능한 사실에 근거한 합리적인 시장 해석을 배제하지 않으며, 출처·기초 사실조차 확보할 수 없으면 `reason:null`을 사용한다.
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
