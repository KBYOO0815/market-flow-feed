# Market Flow 시황 데이터 계약 (v1)

## 발행 경로
- `market-status/index.json`: {schemaVersion:1,updatedAt:ISO-KST,dates:[{date:"YYYY-MM-DD",path:"market-status/YYYY-MM-DD.json"}]}.
- `market-status/YYYY-MM-DD.json`: {schemaVersion:1,date:"YYYY-MM-DD",editions:{"HH:MM":edition}}.
- edition: {date,slot,scheduledFor,asOf,publishedAt,sessionStatus,scope,us,kr,highlights,sources,status}.
- `scope`: "US_KR" | "KR" | "US". `sessionStatus`: 시장별 실제 "PRE" | "REGULAR" | "AFTER" | "CLOSED" | "UNCONFIRMED" 등 구체적 세션 설명 문자열.
- `us`·`kr`: 해당 지역을 분석하지 않은 회차는 null; 분석한 회차는 {summary:string,observedAt:offset-aware ISO8601,indices?:[{name,value,changePct,observedAt,sourceUrl}],flows?:[],themes?:[],notes?:[]} 등 확인된 필드만 사용. 확인 불가능한 값은 null 또는 생략. 중요 수치·사실은 `sources`에 근거를 기재.
- `highlights`: 문자열 배열. `sources`: [{name,url,checkedAt}] 배열, URL은 실제 확인한 HTTPS 원문 링크. `status`: {collection:"success"|"partial",validation:"success",publication:"success"}. 실제 성공 발행 payload에만 publication success 기록.
- 각 회차 고유 키는 한국 날짜+slot, 분석시점은 asOf, 게시시점은 publishedAt. scheduledFor를 소급 조작하지 않는다.
- 보관: GitHub D~D-3까지 4개 한국 달력날짜, 앱에는 D·D-1만. 앱은 index → 날짜별 JSON 조회.
- 지정 회차: 한국 KRX 거래일 06:10/07:10=US_KR, 08:10/09:10/10:10/11:10/12:10/13:10/14:10/15:40/17:10/18:10/19:10/20:10=KR, 23:10=US. 한국 휴장/미국 정규 거래일일 때 06:40=US. 그 외 회차 미발행.
- 거래일은 공식 KRX·NYSE/Nasdaq 실제 일정 검증. 수능일/조기마감 등에 따라 실제 거래세션을 표기. 15:40에 종가 미확정이면 장중 시황으로 기록.
- 최신 원격 HEAD를 읽어 보존·병합, 날짜별+index를 하나의 Git tree/commit으로 원자 저장, HEAD compare-and-swap 후 원격 재조회/검증. 병렬 작업이 겹칠 경우 충돌 재시도. 기존 정상 회차를 더 오래된 asOf로 덮지 않는다.
- 기존 `market-briefing.json`, `featured-stocks` 등 타 기능 파일은 수정 금지.
- 실제 조사/저장에 실패한 데이터를 임의 수치나 빈 성공판으로 발행하지 않는다.
