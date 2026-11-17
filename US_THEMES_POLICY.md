# Market Flow 06:40 미국 테마 — 데이터 계약

> 이 문서는 06:40 미국 테마의 **저장 형식과 앱 호환 규칙만** 정의한다. 거래대금 원천 탐색, Top50 구성 방법, 종목 분류, 테마 발견, 상승 재료 검색·검증 방법은 ChatGPT 정규 예약 작업의 최신 프롬프트가 자율적으로 결정한다.

## 적용 회차

- 미국 테마는 **06:40 브리핑에만** 저장한다.
- 다른 회차는 `usThemes: []`, `usThemeStatus: "not_applicable"`.
- 06:40 `usThemeStatus`: `verified_themes | verified_no_theme | insufficient_data`.
- 최대 3개 테마를 저장한다.

## JSON 필드

테마 기본 필드:

- `rank`
- `theme`
- `weightedChangePct`
- `totalDollarVolume`
- `afterHoursStatus`
- `reason`
- `stocks`
- `relatedKoreanStocks`

종목 기본 필드:

- `ticker`
- `companyName`
- `regularChangePct`
- `dollarVolume`
- `dollarVolumeRank`
- 확인 가능한 경우 시간외 등락률·관측시각·출처

Top50 원자료, 거래대금 정의, 원천, 계산 구성원, 산술 검증 결과 등 감사정보가 필요한 경우 `researchAudit.usThemeEvidence`에 저장한다.

## 데이터 무결성

- 확인되지 않은 수치·순위·시각·종목을 임의 생성하지 않는다.
- `weightedChangePct`와 `totalDollarVolume`은 해당 회차에서 실제 사용한 입력값과 일치해야 한다.
- 자료가 충분하지 않으면 빈 테마 배열과 `insufficient_data` 상태를 사용한다.
- 저장 후 공개 JSON을 재조회해 앱 계약과 일치하는지 확인한다.

---

**미국 테마를 어떤 사이트에서 찾고, 어떤 방식으로 Top50을 만들며, 어떤 재료를 테마로 판단할지는 이 문서가 강제하지 않는다. 정규 예약 작업 프롬프트가 전담한다.**
