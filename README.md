# Market Flow — JSON feeds

단순 운영 구조: **시황: Gemini → Google Drive → GitHub Actions → GitHub JSON → Android 앱**. 뉴스: Claude → Google Drive → GitHub Actions → GitHub JSON → Android 앱. 특징주는 별도.

## 운영 파일

- `market-status.json` — 시황: 07:11 KST(월~토, 미국 휴장일 포함), 15:41 KST(당일 KRX 거래일).
- `market-news.json` — 뉴스: 매일 08:00, 15:20 (KST), 2026-11-28부터.
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

시황 발행은 아래 워크플로를 사용합니다. 특징주 기존 방식은 변경하지 않습니다. 예전 작업과 발행 이력은 이 저장소의 Git 이력 및 보관 기록에서 조회할 수 있습니다.

## 시황 Drive 연동

- Workflow: `.github/workflows/market-status-drive.yml`; UTC 일~금 22:11 / 매일 06:41, 5분 간격 2회 재시도. 이미 발행한 회차는 중복 저장하지 않습니다.
- 미국 입력: `MarketFlow/market-status-us.json`, 한국 입력: `MarketFlow/market-status-kr.json`. 두 파일의 공개 읽기 전용 Drive ID는 `scripts/publish_market_status.py`의 DRIVE_IDS에 설정합니다. 별도 인증이나 저장소 변수가 필요하지 않습니다.
- 입력 필드: date(KST), slot, marketDate(미국: 최근 완료된 정규장 현지 거래일, 한국: 당일 거래일), asOf(실제 관측 시각), content. 기존 파일 ID를 유지하고 UTF-8 JSON으로 갱신합니다.
- XNYS/XKRX 거래일과 실제 정규장 종료 시각은 exchange-calendars 4.13.1을 사용합니다. 임시 휴장 등 거래소 일정 변경은 라이브러리 갱신이 필요합니다.
- 기존 00.39 앱 호환을 위해 date, slot, display, sources를 기계적으로 생성합니다. 미국 회차에 최근 정규장 거래일 배지를 표시하며 marketDate도 보존합니다. 미국 휴장일 및 월요일에도 당일 새로 관측한 보고서를 발행하고 일요일은 건너뜁니다. content는 수정하지 않습니다. 링크 확인 시각이 입력에 없으면 비워 둡니다.
- D/D-1만 보관하며 navigation.next는 빈 배열입니다. 이전 발행 이력은 Git 기록에 보존됩니다. 미연결/휴장/오류는 missing/skipped/failed로 표시합니다.
- 코드 변경 시 단위 테스트 및 미국·한국 양쪽 Drive 읽기 전용 검증을 실행합니다. 수동 실행은 기본 읽기 전용이며 publish 체크 시에만 운영 발행을 시도합니다.
- 2026-11-27 미국·한국 Drive 파일은 연동 테스트용이므로 두 회차 모두 운영 발행하지 않습니다. 이후 미국은 월~토 당일 신규 분석, 한국은 KRX 거래일 신규 분석만 발행합니다.

## 뉴스 Drive 연동

- Claude 매일 07:50/15:10 KST 수집, 08:00/15:20 이전 저장. 폴더 ID `1YBXHGxCZut2F1qLAqF7ryebg8EDyoXrQ`, 파일명 `market-news-YYYY-MM-DD-0800.json` / `market-news-YYYY-MM-DD-1520.json`. 동일 이름의 정상 입력 중 asOf가 가장 최신인 파일을 선택하고 동률이면 실패 처리합니다.
- news 폴더만 링크 공개 뷰어로 설정합니다. 공개 embeddedfolderview HTML에서 정확한 파일명과 ID를 찾고 공개 다운로드 URL로 JSON을 읽습니다. 서비스 계정/API 키 불필요. 공식 Drive API가 아닌 공개 웹 화면에 의존하므로 화면 변경 또는 목록 제한 시 실패할 수 있습니다. 장기 운영 시 폴더 내 파일 수 관리가 필요합니다. 상위 폴더 공유 변경 없음.
- Workflow `.github/workflows/market-news-drive.yml`: 매일 08:00/05/10, 15:20/25/30 KST. GitHub 예약 실행 지연 가능. 성공 회차 중복 발행 방지. 수동 기본은 읽기 전용 테스트 파일 검증이며 testOnly 입력은 운영 제외.
- 입력 date, slot, asOf, foreignNews, domesticNews. 각 배열 최대 10개, 기존 뉴스 항목 필드 유지. 빈 배열은 정상 수집 완료일 때만 허용. 날짜/회차/관측 시각/출처/중복 형식 검증 후 기존 앱의 days[].sessions[]로 병합. D/D-1 유지, 기존 정상 회차 보존. 기사 사실 자체는 Claude가 검증합니다.
- 최초 운영일 2026-11-28. 기존 뉴스 JSON은 실제 첫 발행 전까지 유지. 앱, 시황, 특징주 변경 없음.
