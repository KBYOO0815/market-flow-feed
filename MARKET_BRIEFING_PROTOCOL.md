# Market Flow 브리핑 — 최소 데이터 계약

> 이 문서는 앱과 GitHub JSON 사이의 **형식·저장 규칙만** 정의한다. 뉴스 검색·선별·중복 판단·검증·미국 테마·한국장 마감 시황 분석 방법은 ChatGPT 정규 예약 작업이 자율적으로 결정한다.

## 운영
- 공개 파일: `KBYOO0815/market-flow-feed/market-briefing.json`
- 일반 뉴스 회차: 06:40, 08:40, 12:40, 19:40 KST
- 한국 정규장 마감 시황: **15:40 KST, KRX 거래일에만**
- KRX 비거래일: 06:40, 19:40만 발행
- 15:40은 일반 뉴스 시간창의 기준점이 아니다. 19:40 일반 뉴스는 12:40 이후 재료를 조사한다.
- 보관: D~D-3, 최대 4개 달력 날짜
- 같은 date+slot은 하나만 존재하며 갱신 시 다른 정상 회차를 보존한다.

## JSON
최상위:
```json
{"schemaVersion":1,"updatedAt":"ISO8601","days":[]}
```

날짜:
```json
{"date":"YYYY-MM-DD","isKrxTradingDay":true,"sessions":[]}
```

회차 기본 필드:
- `slot`
- `asOf`
- `foreignNews` 최대 10
- `domesticNews` 최대 10
- `usThemes` — 06:40만 사용, 상승 최대 3 + 하락 최대 3 = 총 최대 6
- `marketClose` — 15:40 거래일 회차에만 사용
- `researchStatus`는 필요할 때만 `complete|partial|failed`
- `usThemeStatus`는 필요할 때만 사용

15:40 회차는 `foreignNews: []`, `domesticNews: []`, `usThemes: []`로 두고 `marketClose`를 저장한다.

뉴스 기본 필드:
`id,title,summary,publishedAt,sourceName,sourceUrl,relatedStocks,impactRank,category,region`

- `impactRank`는 국외·국내 각각 1부터 연속.
- `sourceUrl`은 HTTPS.
- `publishedAt <= asOf`.

## 15:40 한국 정규장 마감 시황

```json
{
  "marketClose": {
    "summary": "당일 정규장 핵심 시황",
    "kospi": {"close": 0, "changePct": 0},
    "kosdaq": {"close": 0, "changePct": 0},
    "leadingThemes": [],
    "weakThemes": [],
    "sources": [{"name":"원천명","url":"https://..."}]
  }
}
```

- `summary`, KOSPI/KOSDAQ `close`·`changePct`, 최소 1개 `sources`는 필수다.
- 거래대금·투자자 수급 등 추가 수치는 확인된 경우 `summary`에 포함할 수 있다.
- `leadingThemes`, `weakThemes`는 각각 확인 가능한 대표 테마를 간결하게 기록한다.
- 확인되지 않은 숫자는 만들지 않는다.

## 미국 테마
- `direction: "up" | "down"`
- `theme`
- `reason`
- `weightedChangePct` 선택
- `totalDollarVolume` 선택
- `afterHoursStatus` 선택
- `stocks` 최대 5
- `relatedKoreanStocks` 선택

정확한 탐색 방법이나 Top50 강제 검증 규칙은 GitHub 정책에 두지 않는다.

## 저장
1. 쓰기 전 최신 파일과 SHA를 확인한다.
2. 기존 정상 회차를 보존해 병합한다.
3. 강제 덮어쓰지 않는다.
4. D~D-3만 유지한다.
5. 저장 후 공개 파일을 다시 읽어 실제 반영을 확인한 경우에만 성공으로 보고한다.

**GitHub는 데이터 계약만 담당한다. 검색·선별·검증 판단은 예약 작업이 담당한다.**
