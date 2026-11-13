# 사용자 선별 프롬프트의 서버 적용

NEWS_SELECTION_PROMPT.md가 사용자 선별 기준이다. 새 메타데이터는
2026-11-13 11:50 이후 회차에 적용한다. 기존 발행본과 과거 교정본을 새 규칙으로
재표기하지 않는다. 시간표·3일 보관·비공개 저장소·06:40 미국 테마 규칙은 유지한다.

## 연구와 코드의 역할

연구자가 실제 원문을 읽어 사건·신규 사실·출처 신뢰성·영향 범위·직접 사업관계를
판단한다. 서버가 그 판단을 했다고 꾸미지 않는다. 제목·URL의 문자열 일치만으로
의미가 같은 사건을 완벽히 판정할 수 없다. 코드에는 연구자가 부여한 안정적인
사건/사실 식별자와 실제 시각을 전달해 범위·중복·정렬·기발행 사실을 대조한다.
같은 사실에 임의로 새 키를 발급하는 것은 금지한다.

6개 기존 researchAudit 분야는 유지하되 각 분야에서 사용자 프롬프트의 세부
영역을 빠짐없이 조사한다. 운영 연구 기록에 검색 범위·후보별 원문·시각·판정·
누락 분야를 남긴다. 단순 URL 채우기는 조사 완료가 아니다. 자동 원천 수집의
후보 링크를 검증된 뉴스로 취급하지 않는다. 전망·추정·주관적 주가 영향은
새 사실로 채택하지 않으며, 예시의 해석 문장보다 사용자의 사실 검증 기준을
우선 적용한다. 기업의 실제 가이던스 발표와 검증된 발언 사실은 구분해 쓸 수 있다.

## 실제 조사 시간 범위

최상위 selectionAudit:

```
{
  "mode": "explicit | since_previous | premarket",
  "startAt": "실제 조사 시작 범위(시간대 필수)",
  "endAt": "asOf와 같은 실제 최종 조사시각",
  "previousReleaseAt": "직전 실제 공개본의 releaseAt (explicit은 생략 가능)",
  "previousAsOf": "직전 실제 공개본의 asOf (explicit은 생략 가능)"
}
```

사용자 지정 시작은 inclusive(그 시각 포함). 기본/장전은 직전 공개본의 실제
asOf 이후를 exclusive로 조사해 검토→발행 사이 새 자료 누락을 방지한다.
발행기는 저장된 실제 직전 공개본과 시작 범위를 다시 대조한다. scheduled
releaseAt을 asOf 대신 추정해 쓰지 않는다. 일반 복구 창에서도 목표 발행시각
이후 발생한 사실을 앞 회차에 넣지 않는다. 과거에 발생한 사건의 재보도 시각을
새 사실 시각으로 기록하지 않는다. 공식 확인·실제 합의·공시 등의 후속 사실은
그 새로운 발표 자체의 시각·문장·원문으로 기록한다.

## 뉴스 항목별 selection

06:40 파생 테마 카드 외 모든 뉴스 항목에 아래를 추가한다.

```
{
  "eventKey": "동일 사건에서 변하지 않는 식별자",
  "eventAt": "포함된 신규 사실 중 마지막 실제 발표/관측 시각",
  "newness": "new | followup",
  "verificationStatus": "confirmed",
  "materialType": "event | market_trend",
  "sourceClass": "official | filing | reuters | bloomberg | ft_wsj | major_media | other_reliable",
  "facts": [{"key": "동일 사실에서 변하지 않는 전역 식별자", "occurredAt": "신규 발표/관측 실제시각", "sourceUrl": "HTTPS 원문", "statement": "검증된 새 사실"}],
  "scopeRank": 1,
  "scores": {"impact": 1, "certainty": 1, "novelty": 1, "koreaRelevance": 1},
  "relatedEvidence": [{"stock": "relatedStocks의 실제 이름/코드", "sourceUrl": "직접 사업관계 원문"}]
}
```

scopeRank는 사용자 기준대로 시장전체1/여러업종2/특정업종3/개별기업4.
동일 범주의 네 판단 요소는 내부1~5점으로 기록하고 곱을 계산한다. 점수는
내부 배열 근거이며 투자 의견이나 주가 예측이 아니다. 같은 점수는 새 사실의
실제 시각 내림차순, 식별자 오름차순으로 정렬한다. 국외·국내는 각각 독립 정렬.
한 회차의 같은 사건은 facts를 병합해 하나의 뉴스로 작성한다. 이전 회차와
같은 사건의 실제 새 사실은 newness=followup으로 식별한다. 과거 fact key는
재사용할 수 없다. 출처·제목을 바꿔 재발행하지 않는다.

시장 동향은 market_trend/kind=market_snapshot과 observedAt을 사용한다.
eventAt=observedAt이고 summary에 HH:MM KST를 반드시 표시한다. 기존
10분 이내 관측·15분 만료 검증도 유지한다. 기업 사건을 시장 반응으로 다시
포장하지 않는다. relatedStocks의 모든 이름/코드에 직접 사업관계 근거를 남기며,
연관 종목이 없으면 두 배열 모두 빈 배열로 둔다. sourceClass의 선언만으로
출처가 검증된 것이 아니며 원문 사실성·숫자 대조는 연구자가 수행한다.

## 합성·검증·출력

1. 원문 조사와 후보별 판정을 operations/research/에 실제 저장한다.
2. 06:40은 기존 us_themes.py 합성을 먼저 수행한다(다른 회차 금지).
3. `python3 scripts/editorial_rules.py INPUT OUTPUT [REPORT.md]`로 독립 중요도
   정렬과 필요시 사용자 지정 제목·국외/국내 표를 생성한다.
4. `python3 scripts/prepare_feed.py --stage OUTPUT VALIDATED`로 검증한다.
5. 동일 VALIDATED를 양 저장소 초안에 저장한다. 공개 워크플로가 원격 원본과
   D~D-2 날짜별 기록을 같은 커밋 기준으로 읽어 기발행 fact key를 최종 차단한다.
6. 실제 공개 root·날짜별 회차 일치 확인 후 성공 기록 및 비공개 미러 갱신.

Markdown 표는 운영·채팅 보고 형식이다. APK는 기존 title+summary 화면을
유지한다. 06:40은 기존 합의대로 테마 요약1+국외뉴스최대9+국내뉴스최대10,
다른 회차는 국외뉴스최대10+국내뉴스최대10. 파생 테마 카드를 새 뉴스로 세지 않는다.
미확인 숫자는 삭제하거나 '확인 불가'로 표기한다. 중요한 핵심 사실 자체가
확인되지 않으면 제외한다. 분류·점수·관련 근거가 미완료인 후보도 선정하지 않는다.
