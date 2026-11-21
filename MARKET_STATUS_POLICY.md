# Market Flow 시황 데이터 계약 (v2)

## 목적
시황 JSON은 **분석·검증용 원시 데이터**와 **앱 표시용 display 데이터**를 분리한다.
시장 판단은 서버/예약 작업이 끝내며 Android 앱은 display를 순서대로 렌더링만 한다.

## 발행 경로
- `market-status/index.json`: `{schemaVersion:1,updatedAt:ISO-KST,dates:[{date,path}],navigation:{previous:[],today:[],next:[]}}`
- `market-status/YYYY-MM-DD.json`: `{schemaVersion:1,date,editions:{"HH:MM":edition}}`
- 보관은 KST D-day·D-1 최대 2개 달력 날짜다.

## edition 원시 데이터
기존 검증·감사용 필드는 유지한다.
- `date,slot,scheduledFor,asOf,publishedAt,sessionStatus,scope,us,kr,highlights,sources,status`
- `scope`: `US_KR | KR | US`
- `us/kr`: 분석하지 않은 지역은 null. 분석한 지역은 `summary,observedAt,indices,flows,themes,notes` 등 실제 확인된 필드만 기록한다.
- 확인하지 못한 수치는 만들지 않고 null 또는 생략한다.
- `sources`: 실제 확인한 HTTPS 원문만 기록한다.
- `status.publication:"success"`는 원격 재조회까지 성공한 payload에만 기록한다.

## 앱 표시용 display — 필수
신규 정상 발행 edition에는 다음 `display`를 반드시 포함한다.

```json
{
  "display": {
    "headline": "코스피·코스닥 급락 마감",
    "badges": ["한국", "정규장 마감", "일부 확인"],
    "observedAt": "2026-11-20T15:30:00+09:00",
    "sections": [
      {
        "id": "kr-indices",
        "title": "주요 지수",
        "kind": "metrics",
        "items": [
          {"label":"KOSPI","value":4869.96,"changePct":-5.21,"note":"15:30 종가"}
        ]
      },
      {
        "id": "flows",
        "title": "수급",
        "kind": "bullets",
        "items": ["외국인 -1.13조원 · 기관 -0.95조원 · 개인 +1.59조원"]
      },
      {
        "id": "drivers",
        "title": "시장 핵심",
        "kind": "bullets",
        "items": ["반도체·AI 인프라 약세", "장중 매도 사이드카 발동"]
      },
      {
        "id": "watch",
        "title": "주의·확인",
        "kind": "bullets",
        "items": ["미국 AI·반도체 재료와 외국인 매도 흐름 주시"]
      }
    ]
  }
}
```

### display 규칙
- `headline`: 한 화면에서 바로 이해할 수 있는 **한 줄 핵심 결론**. 장황한 원문 요약을 복사하지 않는다.
- `badges`: 최대 4개. 예: `한국/미국`, `장전/정규장/마감/애프터/프리마켓`, `일부 확인/검증 완료`.
- `observedAt`: display 전체를 대표하는 실제 관측시각.
- `sections`: 사용자가 읽을 가치가 있는 항목만 넣으며 순서 자체가 표시 순서다. 앱이 재정렬하지 않는다.
- `kind:"metrics"`: `items:[{label,value,changePct?,note?}]`. `value`는 number|string|null.
- `kind:"bullets"`: `items:string[]`.
- `kind:"text"`: `text:string`. 꼭 필요한 짧은 설명에만 사용한다.
- 같은 내용을 headline/section/notes에 반복하지 않는다.
- ISO 시각, 원천 URL, 내부 검증 문구, 긴 영문 sessionStatus를 본문용 텍스트로 반복하지 않는다.
- 출처는 기존 `sources`에 두고 앱은 **출처명만 표시하며 URL은 링크 동작에 사용**한다.
- 원시 `us/kr`는 감사·재검증용이며 앱 본문은 `display`를 우선 사용한다.
- 신규 섹션을 추가할 때 기존 `metrics|bullets|text` 중 하나로 표현하면 앱 업데이트 없이 표시할 수 있다.

## 회차
- 한국 KRX 거래일:
  - 06:10, 07:10 = US_KR
  - 08:10, 09:10, 10:10, 11:10, 12:10, 13:10, 14:10, 15:40, 17:10, 18:10, 19:10, 20:10 = KR
  - 23:10 = US
- 한국 휴장이고 직전 미국 정규장이 실제 거래된 경우 06:40 = US.
- 특별 거래시간은 실제 공식 세션을 따른다.

## 발행
- 최신 원격 HEAD를 읽어 기존 정상 회차를 보존·병합한다.
- 날짜별 JSON과 index를 안전하게 갱신하고 원격 재조회로 확인한다.
- 기존 정상 회차를 더 오래된 `asOf`로 덮지 않는다.
- 타 피드(`market-briefing.json`, `featured-stocks`)는 수정하지 않는다.
- 수집·분석·display 구성·검증 중 하나라도 실패하면 정상 발행으로 표시하지 않는다.

## 실행 감사 로그
- 모든 정규 실행은 루트 `RUN_AUDIT_POLICY.md`를 따른다.
- `display` 생성·검증은 `validation_done` 이전에 완료한다.
- 미발행 시 `failedStep,errorCode,errorMessage`와 마지막 체크포인트를 남긴다.


## 앱 시간축 navigation
앱 사용자가 과거·현재·다음 회차를 모두 예측 가능하게 볼 수 있도록 `market-status/index.json`에 서버 승인 시간축을 저장한다. Android 앱은 거래일·휴장일·다음 거래일을 계산하지 않고 이 배열을 그대로 사용한다.

```json
{
  "navigation": {
    "previous": [
      {"date":"2026-11-20","slot":"23:10","state":"published"}
    ],
    "today": [
      {"date":"2026-11-21","slot":"06:40","state":"published"},
      {"date":"2026-11-21","slot":"15:40","state":"skipped","reason":"KRX 휴장"}
    ],
    "next": [
      {"date":"2026-11-23","slot":"06:10","state":"scheduled"},
      {"date":"2026-11-23","slot":"07:10","state":"scheduled"}
    ]
  }
}
```

### navigation 규칙
- `previous`: 직전 유효 시황 날짜의 **논리 회차 전체**를 시간순으로 기록한다. 발행된 회차뿐 아니라 미발행 회차도 포함한다.
- `today`: 오늘의 **논리 회차 전체**를 시간순으로 기록한다.
- `next`: 오늘 이후 가장 가까운 **다음 유효 시황 날짜의 논리 회차 전체**를 시간순으로 기록한다.
- `state`: `published | scheduled | skipped | missing | failed`.
- `published`: 운영 JSON에 정상 발행된 회차.
- `scheduled`: 아직 도래하지 않은 정상 예정 회차.
- `skipped`: 휴장·세션 미운영 등 정책상 정상적으로 건너뛰는 회차. 가능하면 `reason`을 기록한다.
- `missing`: 도래했지만 운영 JSON이 없고 정상 skip 근거도 없는 회차.
- `failed`: 감사 로그에서 실패가 확인된 회차. 가능하면 `reason` 또는 `errorCode`를 기록한다.
- 앱은 navigation 항목을 임의로 숨기거나 재분류하지 않는다.
- 현재 선택은 navigation 전체에서 가장 최근의 `published` 회차를 기본으로 한다. 사용자가 과거/미래/skip/missing 회차를 직접 선택할 수 있다.
- `scheduled/skipped/missing/failed` 회차를 선택하면 앱은 데이터를 지어내지 않고 서버 상태와 reason만 표시한다.
- 다음 유효일 계산은 서버/예약 작업 책임이다. 앱에서 요일·KRX 달력·미국장 달력을 계산하지 않는다.
