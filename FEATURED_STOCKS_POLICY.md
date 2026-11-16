# Market Flow 특징주 계약 v3

예약은 기존 ChatGPT `Automation_19be7cd0af808191aecbcc421c15a01c` 하나를 유지한다. KST 09:40/11:40/13:40/15:40/20:10, 공식 확인된 KRX 거래일에만 실행한다. 서버에는 별도 cron을 두지 않는다. scheduled_for의 원래 releaseAt, 실제 asOf/observedAt/retrievedAt/reviewedAt/publishedAt은 구분한다. 지연 시 과거 시세를 만들지 않는다. 뉴스 브리핑은 변경하지 않는다.

## 정량 계약

schemaVersion=3, turnoverBasis=KRX_NXT, universeSize=100, amountUnit=KRW, rateBasis=KRX_PREVIOUS_CLOSE. KOSPI/KOSDAQ 개별기업 COMMON/PREFERRED만 허용한다. ETF/ETN/SPAC/REIT/FUND/BOND/기타는 제외한다. 종목 유형은 classificationVerified와 HTTPS classificationSourceUrl로 확인하며 Naver type=ST만으로 확정하지 않는다.

전체 security master, 전체 KRX venue-only 금액, 공식 전체 NXT 거래대상과 각 종목의 venue-only 금액을 같은 거래일로 대조한다. 잘린 두 Top100 목록만으로 순위를 확정하지 않는다. 현재 구현은 더 엄격한 full_universe 증명을 사용한다. nxtEligibleCodes 전체에 실제 NXT quote가 있어야 한다. 공식 거래대상 미포함인 경우에만 증빙을 남기고 0을 허용한다. 미조회/404/장애는 0이 아니다.

stocks는 통합금액 내림차순/동률 코드순 정확히100종목이다. 수집 단계 rankingProof.allMarketRows에는 재계산 가능한 전체 적격 후보, 각 거래소의 정규화 원자료와 완전성 근거를 남긴다. 공개 단계에서는 해당 증빙을 collections/featured-proofs/의 불변 blob에 한 번 저장하고 rankingProof.evidencePath/evidenceBlobSha로 참조한다. 공개 root·날짜별 회차에는 전체 Top100 원자료를 유지하되 전체시장 증빙을 매 회차 중복 전송하지 않는다. 공개 검증기는 동일 blob SHA의 전체 증빙을 읽어 순위를 재검증한다. 통합금액=krxTradeAmount+nxtTradeAmount. 가격, KRX 전일 정규 종가 및 출처로 changeRate를 재계산한다. 신규상장 공식 기준가는 별도 comparison으로 근거를 명시하며 유효 비교가 불가능하면 비교불가로 표시한다.

15:40 장후 KRX 가격을 사용할 때도 원문 장후 자체 등락률(정규장 종가 대비)을 복사하지 않는다. 당일 KIS 기준가와 락구분00을 확인해 전일 정규장 기준으로 실제 KRX 가격의 수익률을 다시 계산한다. 권리락 등 비교기준이 불명확한 Top100 종목은 발행을 차단한다. 같은 날 누적 금액을 조회한 비선정 저유동성 종목의 마지막 체결시각과 수집시각을 구분하며, 실제 선별 Top100의 시세 신선도는 별도로 검증한다.

20:10은 KRX REGULAR_CLOSE와 closeConfirmed, NXT NXT_FINAL과 closeConfirmed를 요구한다. 장후 시세를 KRX 종가로 바꾸지 않는다. 각 금액은 시장별 turnoverScope와 tradeDate, sourceUrl, observedAt, retrievedAt을 갖는다.

selectedStockCodes는 비교 가능한 changeRate>=4.00 전체이며 누락/추가 금지. 이 종목들만 themes 또는 individualStocks에 정확히 한 번 배정한다. 테마는 최소2종목, 개수 상한 없음, industry 또는 shared_catalyst 근거를 갖는다. 서로 다른 원인을 공통 재료로 단정하지 않는다. 테마 가중값은 포함된 +4% 이상 종목들만의 통합금액 가중평균이며 전체 산업 지수가 아니다. 테마는 가중상승률순, 개별은 상승률순. 하락 대표주 관측이 있으면 부분 강세라고 설명한다.

## 이유 검증

reason=null이면 앱에 `당일 상승 이유 확인 안 됨`을 표시한다. 확인한 이유에는 summary, HTTPS sourceUrl, 최초 publishedAt, 실제 checkedAt, facts, verificationStatus=confirmed, causality(source_attributed/related_fact_only)를 기록한다. 당일 최초 사실과 실제 관측 cutoff 이전 여부를 검증한다. 숫자를 추정하지 않는다. 투자판단/목표주가/루머 제외. 별도 최종 테마 판정/마지막 순위 요약 금지.

## 공개·보관·전환

운영 root `featured-stocks.json`, 날짜별 `featured-stocks/YYYY-MM-DD.json`, index `featured-stocks/index.json`, private mirror `data/featured-stocks.json` 유지. v3 root는 최신 회차 필드와 days(날짜별 editions)를 함께 보관한다. D..D-3 달력4일, 각 날짜 최대5슬롯, 최신순. 동일 회차 최신 검증자료로 교체하며 다른 회차 보존. 휴일/미발행에 가짜 회차 생성 금지.

동일 HEAD로 전체 읽기→병합→Git tree/commit 원자 갱신(non-force)→충돌시 최신 HEAD 재조회 최대5회→해당 commit root/일별/index/FIFO 삭제 재조회. 첫 v3 전환 시 기존 root blob을 backups/featured-stocks/pre-v3-<blob>.json에 보존한다. 구형 v1/v2는 앱에서 과거자료로 읽되 서버 재발행은 금지한다. 구 APK는 v3를 거절하므로 새 APK 설치가 필요하다. 새 검증 전 기존 정상 root를 교체하지 않는다.

공개 성공과 private 미러 성공을 구분한다. APP_MIRROR_TOKEN이 설정돼야 서버에서 private 미러 저장/재조회가 가능하다. 미설정이면 public_published_mirror_pending으로 보고하고 완료라 하지 않는다.

## 실제 수집 어댑터의 보류 조건

`featured_integrated.py`는 Naver KRX/NXT와 NXT 공식 원자료를 실제 재조회하고 collection-artifacts에 오류까지 남긴다. 기본 자동 어댑터 `featured_naver_v3.py`는 한국투자증권 당일 전체 종목 마스터(KOSPI/KOSDAQ), Naver 전체 KRX 목록의 그룹/시장, SPAC·우선주 코드를 교차 확인한다. ST 주권과 FS 외국주권은 기업 주식으로 포함하며 DR 및 기타 증권은 제외한다. 전체 마스터에 있으나 순위 목록에서 누락된 종목도 실제 상세 조회로 확장한다. 전체 적격 KRX 종목과 NXT 공식 거래대상 전체의 venue별 detail을 bounded 병렬 조회한다. 원문 거래일/체결시각/세션/금액/전일대비를 검증하며 5분 초과나 한 경계 후보의 미확인도 발행을 보류한다. 신규상장은 전일종가가 없음을 명시하고 공식 대체 기준 검증 전 선별에서 제외한다. API 접근제한을 우회하지 않는다.

외부 대체 normalized integratedSourcePackage를 지정하는 경우에도 실제 재조회 rawResponses와 일치해야 한다. 20:10 NXT 공식 최종집계 확인 및 KRX 종가 원천이 확인되지 않으면 자동 정규화를 중단한다. 어댑터 코드/시험 통과를 실데이터 정상 발행으로 보고하지 않는다.

## 실행

수집요청 requests/featured-collection.json → collection_worker (수집만) → 실제 원문 조사 review → featured_stocks.py stage → drafts/featured-stocks.json → featured_watch → 공개/미러 검증. `mode=collect_probe`와 시험 fixtures는 발행 불가. 휴장 검증결과는 skipped_non_trading_day. source failure는 collection_failed. 공개 성공은 원격 재조회 후만 인정한다.
