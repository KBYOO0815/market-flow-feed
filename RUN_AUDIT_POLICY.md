# Market Flow 실행 감사 로그 계약 (v2)

## 목적
예약 작업의 "실행됨", "분석됨", "검증됨", "발행됨"을 분리해 기록한다.
작업이 중간에 종료되어도 **마지막으로 도달한 단계와 다음에 하려던 단계**가 남아야 한다.
예약 시스템의 `completed`는 발행 성공을 뜻하지 않는다.

## 저장 경로
- 뉴스: `run-audit/news/YYYY-MM-DD/HHMM.json`
- 특징주: `run-audit/featured-stocks/YYYY-MM-DD/HHMM.json`
- 시황: `run-audit/market-status/YYYY-MM-DD/HHMM.json`
- KST D-day·D-1만 보관한다.
- Android 앱은 감사 로그를 읽지 않는다.

## 가장 중요한 규칙 — 시작 로그를 먼저 쓴다
정규 작업은 정책 파일을 읽은 직후, 시장 조사·웹 검색·데이터 수집·검증보다 **먼저** 해당 회차 감사 파일을 생성/갱신한다.

첫 체크포인트 예:
```json
{
  "schemaVersion": 2,
  "feed": "market-status",
  "date": "2026-11-20",
  "slot": "14:10",
  "scheduledFor": "2026-11-20T14:10:00+09:00",
  "startedAt": "2026-11-20T14:05:15+09:00",
  "updatedAt": "2026-11-20T14:05:16+09:00",
  "status": "running",
  "phase": "run_start",
  "lastCompletedStep": "run_start",
  "nextStep": "calendar_session_check",
  "errorCode": null,
  "errorMessage": null,
  "publication": {
    "attempted": false,
    "success": false,
    "commitSha": null,
    "readbackVerified": false
  },
  "steps": [
    {"name":"run_start","status":"success","startedAt":"...","finishedAt":"..."}
  ]
}
```

이 시작 로그가 없으면 "실행은 기록됐지만 감사 로직 자체가 시작되지 않음"으로 판정한다.

## 체크포인트
모든 미세 동작마다 커밋하지 않는다. 최소 다음 경계에서 감사 파일을 갱신한다.

1. `run_start` — 작업 시작 직후
2. `preflight_done` — 거래일/세션/회차 해석 완료
3. `collection_done` — 필요한 원천 수집 완료
4. `analysis_done` — 분석·분류 완료
5. `validation_done` — payload/데이터 계약 검증 완료
6. `publication_done` — 운영 JSON 커밋 완료
7. `readback_done` — 원격 재조회 완료, 최종 상태 확정

특징주처럼 수집이 긴 작업은 `krx_collection`, `nxt_collection`, `top100_validation`, `reason_research` 뒤에도 체크포인트를 추가할 수 있다.

각 체크포인트에는 최소한:
- `updatedAt`
- `status`
- `phase`
- `lastCompletedStep`
- `nextStep`
- 해당 단계의 실제 건수/출처/오류(확인 가능한 경우)
를 기록한다.

다음 단계에 들어가기 직전에는 그 단계의 `status:"running"`도 기록한다. 따라서 중간 종료 시 마지막 파일만 봐도 어느 단계에서 멈췄는지 알 수 있어야 한다.

## 최종 status
- `running`: 아직 실행 중이거나 비정상 종료로 최종화되지 않음
- `published`: 운영 JSON 저장 + 원격 재조회까지 성공
- `failed`: 필수 단계 오류로 미발행
- `partial`: 조사/분석 일부 성공했으나 발행 조건 미충족
- `skipped`: 휴장·세션 미운영 등 정책상 정상 미발행

`skipped`도 감사 로그를 반드시 남긴다.

## 오류 분류
오류 코드는 가능한 한 아래 범주를 사용한다. 실제 원인을 모르면 더 구체적으로 추정하지 않는다.

- `AUTOMATION_NOT_STARTED`
- `AUDIT_NOT_STARTED`
- `PREFLIGHT_REJECTED`
- `SOURCE_UNAVAILABLE`
- `SOURCE_INCOMPLETE`
- `STALE_DATA_ONLY`
- `ANALYSIS_INCOMPLETE`
- `DATA_CONTRACT_CONFLICT`
- `PAYLOAD_VALIDATION_FAILED`
- `GITHUB_READ_FAILED`
- `GITHUB_WRITE_FAILED`
- `GITHUB_CONFLICT`
- `REMOTE_READBACK_FAILED`
- `AUDIT_WRITE_FAILED`
- `UNEXPECTED_EARLY_EXIT`

외부 원천의 실제 HTTP 코드나 GitHub 오류 메시지가 있으면 별도 필드에 원문 그대로 기록한다. 비밀정보·토큰·쿠키·인증 헤더는 기록하지 않는다.

## 조기 기동
예약 플랫폼이 논리 회차보다 일찍 시작해도 그것만으로 실패·skip 처리하지 않는다.
`scheduledFor`와 `slot`은 예정 회차를 유지하고, `startedAt`, `asOf`, `observedAt`은 실제 시각을 기록한다.
예: 14:10 예약이 14:05에 시작되면 14:10 회차로 실행하되 관측값은 14:05 기준임을 명시한다.

## 발행 성공 판정
다음을 모두 만족해야 `published`다.
- 필요한 수집/분석 완료
- payload 검증 성공
- 운영 JSON 저장 성공
- 커밋 SHA 확인
- 원격 재조회 일치

하나라도 안 되면 published로 기록하지 않는다.

## GitHub 감사 파일 쓰기 실패
감사 파일 자체를 못 쓰면 작업을 계속할 수는 있지만, 최종 응답 첫 줄에 반드시:
`AUDIT_FALLBACK feed=<feed> date=<date> slot=<slot> status=<status> phase=<phase> lastCompletedStep=<step> errorCode=<code> error=<actual error>`
를 남긴다.

가능하면 감사 파일 쓰기를 1회 재시도한다. 실패를 숨기거나 success로 바꾸지 않는다.

## 독립 감시 작업의 판정 순서
감시는 도래한 각 회차에 대해 다음 네 자료를 대조한다.
1. 예약 작업 run record: scheduled_for, started_at, completed_at, recorded_status
2. 예약 작업 latest_result/content_text
3. 회차 감사 파일
4. 운영 JSON

판정:
- run record 없음 → `AUTOMATION_NOT_STARTED`
- run record 있음 + 감사 파일 없음 → latest_result를 읽어 원인을 찾고, 없으면 `AUDIT_NOT_STARTED`
- 감사 파일 status=running인데 실행 종료 → `UNEXPECTED_EARLY_EXIT`, phase/lastCompletedStep으로 중단 위치 보고
- audit=published + 운영 JSON 없음 → `REMOTE_STATE_MISMATCH`
- 운영 JSON 있음 + audit 미완료 → `AUDIT_INCOMPLETE`
- latest_result와 audit가 충돌 → `AUDIT_RESULT_MISMATCH`

감시는 단순히 "원인 확인 불가"라고 쓰지 않는다. 확인 가능한 가장 좁은 단계까지 판정한다.

## 최종 응답
모든 정규 작업은 사용자용 설명과 별개로 최종 결과에 최소 다음 정보를 포함한다.
`RUN_RESULT feed=<feed> date=<date> slot=<slot> status=<status> phase=<phase> commit=<sha|null> audit=<path|fallback>`

이 한 줄은 GitHub 감사 로그와 예약 실행 결과를 서로 교차검증하기 위한 것이다.
