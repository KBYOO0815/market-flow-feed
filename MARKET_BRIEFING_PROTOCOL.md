# Market Flow 브리핑 — 데이터 계약 및 GitHub 발행 규칙

> 이 문서는 **앱과 GitHub JSON 사이의 데이터 형식·저장·발행 규칙만** 정의한다. 뉴스 검색어, 검색 원천·횟수·순서, 후보 수집, 중요도 판단, 중복 판정 방법, 사실 검증 방법, SEC/DART 탐색 방법, 기업·CEO SNS 탐색 방법은 **ChatGPT 브리핑 정규 예약 작업**이 자율적으로 결정한다. 이 문서를 AI 뉴스 분석 지침으로 사용하지 않는다.

## 운영 구조

- **정규 발행:** ChatGPT 예약 `Automation_f7a1c2f075188191b451d7a9050c333d` → 신규 재료 조사·분석 → 최종 JSON 생성 → GitHub 공개 저장소 `KBYOO0815/market-flow-feed`에 직접 저장 → 원격 재조회 → 앱 조회.
- **독립 감시:** `6afafb9de2288191a51add93c667ed60`은 발행 누락·손상·품질 이상을 점검하고 필요한 경우 안전하게 복구한다.
- GitHub Actions, 구형 draft/publisher/request 경로는 현행 브리핑 발행 경로가 아니다.
- 앱 개발 저장소의 문서는 참고용 미러이며, 공개 feed 저장소의 이 계약과 실제 앱 파서가 데이터 호환 기준이다.

## 회차와 조사 구간

- Asia/Seoul 기준 정규 회차: **06:40, 08:40, 12:40, 19:40**.
- KRX 비거래일에는 **06:40, 19:40**만 정상 회차다.
- 각 회차는 원칙적으로 **직전 도래 회차의 실제 `asOf` 초과부터 현재 회차의 실제 조사 cutoff까지 새로 공개된 사실**을 저장한다.
- `asOf`는 실제 조사 cutoff다. 예약 시각이나 임의 시각으로 만들지 않는다.
- 과거 누락·partial 복구는 원래 시간창을 보존하며 현재 회차 신규 사실로 위장하지 않는다.

## 공개 JSON 계약

공개 파일은 `market-briefing.json` 하나이며 `schemaVersion: 1`을 사용한다.

최상위 기본 구조:

```json
{
  "schemaVersion": 1,
  "updatedAt": "ISO8601",
  "researchState": {},
  "days": []
}
```

- `days`: 최신순 날짜 데이터. **D~D-3, 4개 달력 날짜 범위**만 유지한다.
- 날짜 객체: `date`, `isKrxTradingDay`, `sessions`.
- 회차 객체 기본 필드: `slot`, `asOf`, `researchStatus`, `usThemeStatus`, `usThemes`, `foreignNews`, `domesticNews`.
- 같은 `date + slot`은 하나만 존재한다. 정정·복구 시 해당 session을 교체하고 다른 정상 회차는 보존한다.
- 존재하지 않는 날짜·회차를 빈 성공 데이터로 만들지 않는다.

## 뉴스 데이터 계약

- `foreignNews`: 최대 10개.
- `domesticNews`: 최대 10개.
- 각 배열의 `impactRank`는 1부터 연속이다.
- 뉴스 기본 필드: `id,title,summary,publishedAt,sourceName,sourceUrl,relatedStocks,impactRank,category,region`.
- 검증 가능한 경우 `eventKey,eventAt,facts` 등 보조 메타를 추가할 수 있다.
- `sourceUrl`은 HTTPS 실제 근거 URL, `publishedAt`은 확인된 실제 원문/공시/공식발표 시각을 사용한다.
- 확인되지 않은 숫자·시각·출처를 임의 생성하지 않는다.
- 어떤 뉴스를 찾고 선택하며 검증할지는 이 문서가 강제하지 않고 정규 예약 작업이 담당한다.

## 조사 상태 메타데이터

- `researchStatus`: `complete | partial | failed`.
- `researchAudit`, `researchState`, `storageVerification`은 조사·저장 상태를 감사하기 위한 보조 메타데이터다.
- 이 메타데이터는 실제 수행 사실만 기록하며, 특정 검색 키워드·뉴스 원천·후보 개수·검색 횟수를 강제하는 정책으로 사용하지 않는다.
- GitHub 저장 성공과 뉴스 조사 완료는 별개의 상태다.

## 06:40 미국 테마 데이터 계약

- `usThemes`는 **06:40 회차에만** 최대 3개 저장할 수 있다.
- 다른 회차는 `usThemes: []`, `usThemeStatus: "not_applicable"`.
- 06:40 `usThemeStatus`: `verified_themes | verified_no_theme | insufficient_data`.
- 테마 기본 필드: `rank,theme,weightedChangePct,totalDollarVolume,afterHoursStatus,reason,stocks,relatedKoreanStocks`.
- 종목 필드는 앱이 사용하는 `ticker,companyName,regularChangePct,dollarVolume,dollarVolumeRank` 및 확인 가능한 시간외 필드를 포함할 수 있다.
- 계산·원천·Top50 증거 등 상세 감사정보는 `researchAudit.usThemeEvidence`에 기록할 수 있다.
- 미국 테마의 원천 탐색·Top50 구성 방식·테마 판정·재료 검증 방법은 **정규 예약 작업 프롬프트가 전담**하며 이 문서에서 고정하지 않는다.

## GitHub 발행·보존 규칙

1. 작업 시작 시 최신 공개 JSON과 현재 blob SHA를 읽는다.
2. 최종 검증된 session만 기존 정상 데이터에 병합한다.
3. 쓰기 직전 최신 HEAD/SHA를 다시 확인하고 충돌 시 재조회·재병합한다.
4. 강제 덮어쓰기하지 않는다.
5. 저장 후 공개 `market-briefing.json`을 다시 읽어 대상 session, JSON 구조, 날짜 범위, 다른 회차 보존 여부와 실제 저장 내용을 확인한 뒤에만 발행 성공으로 보고한다.
6. D~D-3 밖 데이터는 제거하되 미완료 조사 상태가 필요하면 콘텐츠가 아닌 감사 메타데이터 범위만 `researchState`에 보존할 수 있다.

## 앱 호환

- 앱은 공개 `market-briefing.json`을 읽어 날짜별 4개 회차를 표시한다.
- 현재 앱 파서 `src/feed.ts`와 `src/editions.ts`가 구조적 호환성의 최종 기준이다.
- 데이터 계약을 변경해 앱 필수 필드나 회차 구조가 달라질 경우 앱 파서와 함께 변경해야 한다.

---

**이 문서는 데이터 계약이다. 뉴스 검색·선별·중복 판단·사실 검증·시장 중요도 판단은 ChatGPT 정규 예약 작업의 프롬프트가 전담한다.**
