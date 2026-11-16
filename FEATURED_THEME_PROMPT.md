# 특징주 v3 연구 지침

FEATURED_STOCKS_POLICY.md와 scripts/featured_v3.py를 따른다. 원래 예약 회차와 실제 관측시각을 구분하고 실제 KRX 거래일을 확인한다. 통합 전체시장 순위가 입증되지 않으면 기존 정상 공개본을 유지한다. KRX 단독 Top100/예전 강한 테마만 규칙은 사용하지 않는다.

1. 서버 수집 raw 자료, NXT 공식 완전 목록, 종목분류 근거 및 가격 기준을 실제 확인한다. HTTP 성공은 금액/종목 유형/완전성 검증이 아니다.
2. 정확한 통합100의 +4% 이상 전체를 추출한다. 실제 회사 사업관계와 공통 원문을 조사한 최소2종목은 테마, 개별 실적/공시/계약/IPO 등은 개별로 분류한다. 같은 업종이라도 개별 원인을 하나의 공통 상승 재료로 바꾸지 않는다.
3. 모든 선별 종목은 테마 또는 개별에 정확히 한 번 등장한다. 확인 안 된 이유는 reason=null, 표시문구는 `당일 상승 이유 확인 안 됨`. 부족한 자료를 만들어 채우지 않는다.
4. 각 테마 membershipEvidence[{code,sourceUrl,fact}], groupingBasis(industry/shared_catalyst), reason, 필요시 대표주 하락 관측 representativeObservations/context를 기록한다. 공통 상승재료를 주장하려면 당일 실제 원문을 검증한다.
5. reason은 summary/sourceUrl/publishedAt/checkedAt/facts/verificationStatus=confirmed/causality를 갖는다. 직접 인과 보도는 source_attributed, 단순 관련 사실은 related_fact_only. 원문 최초 시각과 수치를 확인한다. 루머/전망/목표주가/투자판단 제외.
6. review에는 실제 reviewedAt, themes, individualStocks[{code,reason}]를 기록한다. 새 원문을 검증하기 전 unknown을 confirmed로 바꾸지 않는다. 전체선별을 확인한 뒤 stage/validate를 실행한다.
7. 출력은 테마 및 개별 영역만, 종목/상승률/통합거래대금/검증 이유/출처를 표시한다. 테마 가중값은 포함 +4% 종목 기준임을 명시한다. 최종 테마 판정 표/마지막 순위 요약 금지.
8. 수집·검증·초안·공개·미러·앱·APK 상태를 따로 보고한다. 시험자료를 실데이터처럼 발행하지 않는다.
