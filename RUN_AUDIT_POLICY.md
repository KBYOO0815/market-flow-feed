# Market Flow 실행 감사 로그 계약 (v1)

## 목적
정규 예약 작업의 **실행 완료**와 **데이터 발행 성공**을 분리한다. 미발행·부분 실패가 발생하면 어느 단계에서 왜 중단됐는지 회차별로 재구성할 수 있어야 한다.

## 저장 경로
- 뉴스: `run-audit/news/YYYY-MM-DD/HHMM.json`
- 특징주: `run-audit/featured-stocks/YYYY-MM-DD/HHMM.json`
- 시황: `run-audit/market-status/YYYY-MM-DD/HHMM.json`
- 운영 감사 로그도 KST 기준 D-day·D-1만 유지한다. D-2 이하는 다음 성공적인 GitHub 쓰기 시 삭제한다.
- 감사 로그는 앱이 읽지 않는다. Android 앱 계약과 독립이다.

## 상태
최종 `status`는 다음 중 하나다.
- `published`: 최종 운영 JSON 커밋과 원격 재조회까지 성공
- `failed`: 실행은 시작했으나 필수 단계 실패로 미발행
- `skipped`: 휴장·세션 미운영 등 정책상 정상 미발행
- `partial`: 일부 조사/수집은 성공했으나 완전 발행 조건 미충족

예약 시스템의 `completed`는 위 상태를 대체하지 않는다.

## 필수 필드
```json
{
  "schemaVersion": 1,
  "feed": "featured-stocks",
  "date": "2026-11-20",
  "slot": "08:40",
  "scheduledFor": "2026-11-20T08:40:00+09:00",
  "startedAt": "2026-11-20T08:42:52+09:00",
  "finishedAt": "2026-11-20T08:46:58+09:00",
  "status": "failed",
  "failedStep": "top100_validation",
  "errorCode": "SOURCE_INCOMPLETE",
  "errorMessage": "검증에 필요한 원천을 완전하게 확보하지 못함",
  "steps": [],
  "publication": {
    "attempted": false,
    "success": false,
    "commitSha": null,
    "paths": [],
    "readbackVerified": false
  }
}
```

실제 값만 기록한다. 확인되지 않은 수치·오류 원인을 추정해 채우지 않는다.

## 단계 기록
각 `steps[]` 원소는 최소 `name,status,startedAt,finishedAt`을 가진다. 가능한 경우 `counts,sources,errorCode,errorMessage`를 추가한다.

권장 단계명:
- 공통: `run_start`, `calendar_session_check`, `source_collection`, `analysis`, `payload_validation`, `github_publish`, `remote_readback`
- 뉴스: `foreign_search`, `domestic_search`, `dedup_ranking`
- 특징주: `krx_collection`, `nxt_collection`, `top100_validation`, `price_validation`, `reason_research`, `theme_classification`
- 시황: `us_market_collection`, `kr_market_collection`, `source_validation`

0건·미확인·HTTP 오류도 사실대로 기록한다. 예: 검색 후보 0건이면 `counts.candidates=0`. 원천 응답 코드가 확인되면 기록하고, 확인되지 않으면 만들지 않는다.

## 실패 시 기록 우선순위
1. 운영 JSON 발행 성공 시: 운영 JSON과 감사 로그를 가능한 한 같은 원자 커밋에 포함한다.
2. 운영 JSON 발행 전 검증 실패 시: 운영 JSON은 건드리지 않고 감사 로그만 별도 커밋해 실패 원인을 보존한다.
3. GitHub 쓰기 자체가 실패하면 GitHub 감사 로그를 남길 수 없으므로, 예약 작업의 최종 응답 첫 줄에 반드시 다음 형식으로 남긴다.
   `AUDIT_FALLBACK feed=<feed> date=<date> slot=<slot> status=<status> failedStep=<step> errorCode=<code> error=<message>`
4. 작업이 아예 기동하지 않은 경우 자체 로그는 존재할 수 없다. 독립 감시 작업이 예정 회차와 운영 JSON·감사 로그를 대조하여 `not_started_or_no_audit`로 판정한다.

## 발행 성공 판정
다음을 모두 만족해야 `status:"published"`다.
- 필수 원천/분석 단계 성공
- 최종 payload 검증 성공
- GitHub 운영 JSON 저장 성공
- 원격 재조회 내용 일치
- commit SHA 확인

그 외에는 `published`로 기록하지 않는다.

## 보안·용량
비밀번호·토큰·쿠키·인증 헤더 등 비밀정보는 감사 로그에 기록하지 않는다. 검색 결과 전체 본문을 복제하지 않고 URL·건수·오류·단계 상태 중심으로 기록한다.
