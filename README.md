# Market Flow — JSON feeds

단순 운영 구조: **시황: Gemini → Google Drive → GitHub Actions → GitHub JSON → Android 앱**. 뉴스: Claude → Google Drive → GitHub Actions → GitHub JSON → Android 앱. 특징주: Gemini → Google Drive → GitHub Actions → GitHub JSON → Android 앱.

## 운영 파일

- `market-status.json` — 시황: 07:11 KST(월~토, 미국 휴장일 포함), 15:41 KST(당일 KRX 거래일).
- `market-news.json` — 뉴스: 매일 08:00, 15:20 (KST), 2026-11-28부터.
- `featured-stocks-unified.json` — 특징주: 기존 발행 이력 보존. KRX 거래일 09:30/14:40 수집, 09:40/14:50 발행(KST). 테스트 발행 완료; 공개 편집 권한 해제 확인 후 운영 발행 활성화.

시황은 Gemini가 수집·분석하고 GitHub Actions가 Drive 입력 검증·병합·발행을 담당합니다. Android 앱은 JSON을 읽어 표시합니다.

## 운영 규칙

- 확인된 실제 데이터와 출처만 발행하며 없는 수치를 만들어 넣지 않습니다.
- 현재 날짜 및 전날(D/D-1)만 유지합니다.
- `navigation.previous/today/next`는 현재 예약 시각만 포함합니다.
- 실패 시 기존 정상 JSON을 덮어쓰지 않으며, 실제 실패 원인을 예약 실행 결과에 남깁니다.
- 데이터 계약이나 회차를 변경할 때는 예약 작업과 앱을 함께 변경합니다.
- 과거 커밋과 감사 기록은 GitHub 기록으로 추적할 수 있습니다.

**주의:** 기존 설치 APK는 구형 경로를 읽을 수 있으므로 새 APK 설치 전까지 일부 피드가 작동하지 않을 수 있습니다. 통합 파일 기반 앱 소스의 빌드 및 실기기 검증은 별도로 필요합니다.

시황 발행은 아래 워크플로를 사용합니다. 특징주는 자유 검색 방식으로 전환합니다. 예전 작업과 발행 이력은 이 저장소의 Git 이력 및 보관 기록에서 조회할 수 있습니다.

## 시황 Drive 연동

- Workflow: `.github/workflows/market-status-drive.yml`; UTC 일~금 22:11 / 매일 06:41, 5분 간격 2회 재시도. 이미 발행한 회차는 중복 저장하지 않습니다.
- 시황 입력 폴더 `MarketFlow/status` (ID `1MsE_fFlcJPWbIYJrUlC9SzV4CxKPLBSK`). 매회 신규 파일 `market-status-YYYY-MM-DD-0711.json` / `market-status-YYYY-MM-DD-1541.json`. 공개 폴더 목록에서 정확한 이름을 조회하고 최신 적격 asOf를 선택하며 동률이면 실패합니다. 고정 파일 ID는 더 이상 사용하지 않습니다. 폴더 공개 뷰어 권장. 별도 인증/API 키 불필요.
- 입력 필드: date(KST), slot, marketDate(미국: 최근 완료된 정규장 현지 거래일, 한국: 당일 거래일), asOf(실제 관측 시각), content. 매회 새 UTF-8 JSON 파일을 생성합니다. testOnly 입력은 운영 제외합니다.
- XNYS/XKRX 거래일과 실제 정규장 종료 시각은 exchange-calendars 4.13.1을 사용합니다. 임시 휴장 등 거래소 일정 변경은 라이브러리 갱신이 필요합니다.
- 기존 00.39 앱 호환을 위해 date, slot, display, sources를 기계적으로 생성합니다. 미국 회차에 최근 정규장 거래일 배지를 표시하며 marketDate도 보존합니다. 미국 휴장일 및 월요일에도 당일 새로 관측한 보고서를 발행하고 일요일은 건너뜁니다. content는 수정하지 않습니다. 링크 확인 시각이 입력에 없으면 checkedAt을 저장하지 않습니다.
- D/D-1만 보관하며 navigation.next는 빈 배열입니다. 이전 발행 이력은 Git 기록에 보존됩니다. 미연결/휴장/오류는 missing/skipped/failed로 표시합니다.
- 코드 변경 시 단위 테스트 및 미국·한국 양쪽 Drive 공개 목록 읽기 검증을 실행합니다. 당일 파일 또는 market-status-test-us.json / market-status-test-kr.json이 있으면 다운로드와 구조도 검증합니다. 빈 폴더는 다운로드 미검증으로 기록합니다. 수동 실행은 기본 읽기 전용이며 publish 체크 시에만 운영 발행을 시도합니다.
- 2026-11-27 미국·한국 Drive 파일은 연동 테스트용이므로 두 회차 모두 운영 발행하지 않습니다. 이후 미국은 월~토 당일 신규 분석, 한국은 KRX 거래일 신규 분석만 발행합니다.

## 뉴스 Drive 연동

- Claude 매일 07:50/15:10 KST 수집, 08:00/15:20 이전 저장. 폴더 ID `1YBXHGxCZut2F1qLAqF7ryebg8EDyoXrQ`, 파일명 `market-news-YYYY-MM-DD-0800.json` / `market-news-YYYY-MM-DD-1520.json`. 동일 이름의 정상 입력 중 asOf가 가장 최신인 파일을 선택하고 동률이면 실패 처리합니다.
- news 폴더만 링크 공개 뷰어로 설정합니다. 공개 embeddedfolderview HTML에서 정확한 파일명과 ID를 찾고 공개 다운로드 URL로 JSON을 읽습니다. 서비스 계정/API 키 불필요. 공식 Drive API가 아닌 공개 웹 화면에 의존하므로 화면 변경 또는 목록 제한 시 실패할 수 있습니다. 장기 운영 시 폴더 내 파일 수 관리가 필요합니다. 상위 폴더 공유 변경 없음.
- Workflow `.github/workflows/market-news-drive.yml`: 매일 08:00/05/10, 15:20/25/30 KST. GitHub 예약 실행 지연 가능. 성공 회차 중복 발행 방지. 수동 기본은 읽기 전용 테스트 파일 검증이며 testOnly 입력은 운영 제외.
- 입력 date, slot, asOf, foreignNews, domesticNews. 국외·국내 뉴스 개수 상한 없음. 유효한 모든 입력 뉴스를 발행합니다. 1 MiB 입력 파일 안전 제한은 유지합니다. Drive 입력은 기존 검증 필드를 유지하고 앱 발행본에서는 checkedAt, region(배열로 구분), eventKey, factKey 및 수집 감사 정보를 제거합니다. 정상 회차의 빈 usThemes 및 complete 상태도 생략합니다. 빈 배열은 정상 수집 완료일 때만 허용. 날짜/회차/관측 시각/출처/중복 형식 검증 후 기존 앱의 days[].sessions[]로 병합. D/D-1 유지, 기존 정상 회차 보존. 기사 사실 자체는 Claude가 검증합니다.
- 최초 운영일 2026-11-28. 기존 뉴스 JSON은 실제 첫 발행 전까지 유지. 앱, 시황, 특징주 변경 없음.

## 앱용 JSON 최소화 (00.39 호환)

- 세 피드의 기존 날짜/회차 컨테이너 및 navigation 계약은 그대로 유지합니다. 기존 시황의 content는 신규 앱의 구조화된 표를 위해 보존하고 display와 sources는 00.39 필수 호환 필드입니다. 루트의 중복 contentTypes 및 비어 있는 출처 checkedAt만 제거합니다.
- 뉴스는 입력 검증 후 앱에 필요한 기사 정보와 출처만 발행합니다. partial/failed 상태 및 테스트 회차 표시는 보존합니다. 기사 배열 자체로 국내/국외를 구분합니다.
- 기존 특징주 schemaVersion 3 이력은 보존합니다. 신규 자유 검색 결과는 아래 계약을 사용합니다.

## 특징주 Drive 연동 (자유 검색)

- Gemini는 시장 전체를 자유 검색합니다. Top100, +4%, 가중 평균, 거래대금 순위, 테마 개수 제한은 폐기합니다. 입력 date, slot, asOf, marketSummary, themes, individualStocks, outlook. 테마 reason/catalyst 및 종목 changeRate/change 별칭을 허용하고 등락률 문자열을 그대로 보존합니다. 출처 배열은 실제 HTTPS URL이며 운영에서는 비어 있으면 실패합니다.
- 폴더 ID `14eWlknJsA0JvTGe7gwJ_GI0SVwrjnKsf`, 파일명 featured-stocks-YYYY-MM-DD-0940.json / -1450.json. 워크플로는 KRX 거래일 09:40/14:50, 5분 간격 두 번 재시도. 공개 목록 조회 방식의 제한은 뉴스와 동일합니다.
- `analysis`는 정규화한 자유 검색 원문입니다. 00.39는 `analysis`를 직접 읽지 못하므로 임시 호환 어댑터로 기존 themes.reason.summary에 요약, 테마, 종목명·등락률 문자열, 개별주, 관전 포인트를 표시합니다. 가중 상승률·거래대금·종목코드를 만들지 않습니다. 기존 앱 고정 Top100 문구는 적용되지 않음을 화면에 안내합니다. 신규 앱은 analysis를 직접 표시하도록 변경해야 합니다.
- 2026-11-27 두 회차는 testOnly=true 및 화면 경고를 붙여 테스트 발행합니다. 실제 시세/관측 시각/재료 미검증이며 투자 판단 금지. 입력 파일은 변경하지 않습니다. 11/30 이전 운영 발행 금지. 폴더가 링크 공개 편집자 상태이므로 LIVE_ENABLED=False로 운영 발행을 차단합니다. 공유 권한을 뷰어로 바꾼 뒤 확인하여 활성화합니다. 예약 실행은 지연될 수 있습니다. D/D-1 유지, 실패 시 기존 정상 회차 보존.

### 예약 누락 복구
- 기존 발행 시각 유지. 추가 분산 cron으로 당일 미발행 회차를 재조회합니다. 예약 실행은 현재 KST 날짜의 모든 도래 회차를 확인하고, 이미 발행한 회차는 건너뜁니다. 오전 회차도 당일 늦게 복구할 수 있습니다. 날짜·입력 검증 및 특징주 운영 차단은 유지합니다. GitHub 자체 스케줄 누락이나 자정 이후 전날 회차 복구는 보장하지 않습니다.
