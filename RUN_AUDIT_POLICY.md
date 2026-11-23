# Market Flow 간소화 운영 원칙 (2026-11-23)

## 역할
- ChatGPT 정규 예약 작업 3개: 시황·뉴스·특징주 검색, 분석, 수치·출처·JSON 검증, GitHub 발행.
- GitHub: 완성된 JSON 보관 및 버전 관리. Python 검증기·GitHub Actions를 정상 발행의 필수 실행 경로로 사용하지 않는다.
- Android 앱: JSON 조회·최소 구조 검사·화면 표시. 투자 판단이나 데이터 재분석 없음.

## 현재 앱 호환 발행 경로
- 시황: market-status/index.json, market-status/YYYY-MM-DD.json
- 뉴스: market-briefing.json
- 특징주: featured-stocks.json, featured-stocks/index.json, featured-stocks/YYYY-MM-DD.json
- 기존 앱이 이 경로를 사용하므로 앱 전환 검증 전에는 경로를 제거하거나 변경하지 않는다. 최종적으로 피드당 단일 JSON 3개로 통합하는 것은 별도 앱 마이그레이션 단계에서 수행한다.

## 발행 규칙
1. 예약 시각·거래일 정책은 실제 활성 예약 작업의 최신 schedule 및 prompt를 단일 기준으로 삼는다.
2. 원천 URL, 실제 관측시각, 핵심 계산을 예약 작업 안에서 확인한다. 확인 불가 데이터는 만들어내지 않는다.
3. 기존 성공 회차를 보존하면서 최신 GitHub SHA 기준으로 병합하고, 원격 재조회에 성공한 경우만 발행 성공으로 보고한다.
4. 운영 데이터 보관은 KST D-day·D-1. 정상 기록을 임의 삭제하지 않는다.
5. 실패 시 응답에 feed/date/slot/failedStep/실제 오류를 간단히 기록한다. 복잡한 단계별 감사 JSON을 매번 생성할 필요는 없다. 과거 run-audit/ 파일은 보존하며 신규 감사 파일은 선택사항이다.
6. 기존 정책 문서의 구형 회차·Python 필수 실행·단계별 감사 강제 조항이 이 문서와 충돌하면 최신 활성 예약 작업과 이 간소화 원칙을 우선한다.

## 운영 변경
- 시황 :10 및 :40 작업은 하나의 시황 예약 작업으로 통합했다. 구형 :40 작업은 비활성화.
- 독립 감시·복구 예약 작업은 비활성화. 필요 시 재활성화 가능.
- GitHub Python 및 GitHub Actions 파일은 실제 호출 관계를 모두 확인하기 전에는 삭제하지 않는다.
