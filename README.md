# Market Flow — JSON feeds

단순 운영 구조: **시황: Gemini → Google Drive → GitHub Actions → GitHub JSON → Android 앱**. 뉴스·특징주 기존 운영은 별도.

## 운영 파일

- `market-status.json` — 시황: 07:11 KST(직전 미국 정규장 거래일), 15:41 KST(당일 KRX 거래일).
- `market-news.json` — 뉴스: 한국장 거래일 07:40, 11:40, 15:40, 19:40 (KST).
- `featured-stocks-unified.json` — 특징주: 한국장 거래일 08:40, 09:40, 11:40, 13:40, 15:40, 19:40 (KST).

시황은 Gemini가 수집·분석하고 GitHub Actions가 Drive 입력 검증·병합·발행을 담당합니다. Android 앱은 JSON을 읽어 표시합니다.

## 운영 규칙

- 확인된 실제 데이터와 출처만 발행하며 없는 수치를 만들어 넣지 않습니다.
- 현재 날짜 및 전날(D/D-1)만 유지합니다.
- `navigation.previous/today/next`는 현재 예약 시각만 포함합니다.
- 실패 시 기존 정상 JSON을 덮어쓰지 않으며, 실제 실패 원인을 예약 실행 결과에 남깁니다.
- 데이터 계약이나 회차를 변경할 때는 예약 작업과 앱을 함께 변경합니다.
- 과거 커밋과 감사 기록은 GitHub 기록으로 추적할 수 있습니다.

**주의:** 기존 설치 APK는 구형 경로를 읽을 수 있으므로 새 APK 설치 전까지 일부 피드가 작동하지 않을 수 있습니다. 통합 파일 기반 앱 소스의 빌드 및 실기기 검증은 별도로 필요합니다.

시황 발행은 아래 워크플로를 사용합니다. 뉴스·특징주 기존 방식은 변경하지 않습니다. 예전 작업과 발행 이력은 이 저장소의 Git 이력 및 보관 기록에서 조회할 수 있습니다.

## 시황 Drive 연동

- Workflow: `.github/workflows/market-status-drive.yml`; UTC 22:11 / 06:41, 5분 간격 2회 재시도. 이미 발행한 회차는 중복 저장하지 않습니다.
- 미국 입력: `MarketFlow/market-status-us.json`, 고정 Drive 파일 ID. 한국 입력은 `MARKET_STATUS_KR_DRIVE_ID` 저장소 변수에 파일 ID 설정 전까지 미연결입니다.
- 입력 필드: date(KST), slot, marketDate(현지 거래일), asOf(실제 관측 시각), content. 기존 파일 ID를 유지하고 UTF-8 JSON으로 갱신합니다.
- XNYS/XKRX 거래일과 실제 정규장 종료 시각은 exchange-calendars 4.13.1을 사용합니다. 임시 휴장 등 거래소 일정 변경은 라이브러리 갱신이 필요합니다.
- 기존 00.39 앱 호환을 위해 date, slot, display, sources를 기계적으로 생성합니다. content는 수정하지 않습니다. 링크 확인 시각이 입력에 없으면 비워 둡니다.
- D/D-1만 보관하며 navigation.next는 빈 배열입니다. 이전 발행 이력은 Git 기록에 보존됩니다. 미연결/휴장/오류는 missing/skipped/failed로 표시합니다.
- 코드 변경 시 단위 테스트 및 Drive 읽기 전용 검증을 실행합니다. 수동 실행은 기본 읽기 전용이며 publish 체크 시에만 운영 발행을 시도합니다.
- 2026-11-27 Drive 테스트 파일은 직전 미국 휴장으로 발행 대상이 아닙니다. 실제 거래일의 신규 입력만 발행합니다.
