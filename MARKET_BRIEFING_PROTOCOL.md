# Market Flow 브리핑 — 최소 데이터 계약

> 이 문서는 앱과 GitHub JSON 사이의 **형식·저장 규칙만** 정의한다. 뉴스 검색·선별·중복 판단·검증·미국 테마 분석 방법은 ChatGPT 정규 예약 작업이 자율적으로 결정한다.

## 운영
- 공개 파일: `KBYOO0815/market-flow-feed/market-briefing.json`
- 정규 회차: 06:40, 08:40, 12:40, 19:40 KST
- KRX 비거래일: 06:40, 19:40
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
- `researchStatus`는 필요할 때만 `complete|partial|failed`
- `usThemeStatus`는 필요할 때만 사용

뉴스 기본 필드:
`id,title,summary,publishedAt,sourceName,sourceUrl,relatedStocks,impactRank,category,region`

- `impactRank`는 국외·국내 각각 1부터 연속.
- `sourceUrl`은 HTTPS.
- `publishedAt <= asOf`.
- 앱에서 사용하지 않는 `researchAudit`, `researchState`, `pendingWindows`, 후보 감사로그, `eventKey`, `facts` 등은 데이터 계약에 포함하지 않는다.

## 미국 테마
테마는 다음 필드만으로 충분하다.
- `direction: "up" | "down"`
- `theme`
- `reason`
- `weightedChangePct` 선택
- `totalDollarVolume` 선택
- `afterHoursStatus` 선택
- `stocks` 최대 5
- `relatedKoreanStocks` 선택

정확한 테마 탐색 방법이나 Top50 강제 검증 규칙은 GitHub 정책에 두지 않는다.

## 저장
1. 쓰기 전 최신 파일과 SHA를 확인한다.
2. 기존 정상 회차를 보존해 병합한다.
3. 강제 덮어쓰지 않는다.
4. D~D-3만 유지한다.
5. 저장 후 공개 파일을 다시 읽어 실제 반영을 확인한 경우에만 성공으로 보고한다.

**GitHub는 데이터 계약만 담당한다. 검색·선별·검증 판단은 예약 작업이 담당한다.**
