"""06:40 US regular-session turnover top-50 and reviewed theme aggregation.

Turnover is the provider's USD accumulatedTradingValue, NEVER close * volume.
Raw collection and reviewed, publishable theme assignments are separate.
"""
import copy
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import json
import pathlib
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
from source_http import read

KST = dt.timezone(dt.timedelta(hours=9))
NY = ZoneInfo('America/New_York')
EFFECTIVE = dt.date(2026, 11, 16)
PAGE = 'https://stock.naver.com/market/stock/usa'
BASE = 'https://m.stock.naver.com/front-api/worldstock/nation/'
INDEX_URL = BASE + 'indexFutures/list?nationType=USA'
EXCHANGES = {'NASDAQ', 'NYSE', 'AMEX'}
SECURITY_TYPES = {'ORD', 'ADR'}
ROLE = 'us_theme_summary'


def stamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone required')
    return parsed


def number(value):
    if isinstance(value, bool):
        raise ValueError('boolean is not a market number')
    try:
        result = Decimal(str(value).replace(',', ''))
    except InvalidOperation as error:
        raise ValueError('invalid market number') from error
    if not result.is_finite():
        raise ValueError('finite market number required')
    return result


def https(value):
    u = urllib.parse.urlparse(value if isinstance(value, str) else '')
    return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password


def enabled(release):
    return release.astimezone(KST).strftime('%H:%M') == '06:40'


def rank_url(page):
    return BASE + 'stock/list?stockNationType=USA&stockPriceSortType=priceTop&page=' + str(page) + '&pageSize=50'


def basic_url(code):
    return 'https://api.stock.naver.com/stock/' + urllib.parse.quote(code, safe='.') + '/basic'


def fetch(url):
    return json.loads(read(urllib.request.Request(url, headers={'User-Agent': 'MarketFlow/1.0', 'Accept': 'application/json'}), attempts=2))


def collect_snapshot(release_at, get=fetch, now=None, probe=False):
    release = stamp(release_at).astimezone(KST)
    checked = now or dt.datetime.now(KST)
    if not enabled(release) or release.weekday() >= 5:
        raise ValueError('US themes are only collected for weekday 06:40 editions')
    if not probe and not release - dt.timedelta(minutes=30) <= checked <= release + dt.timedelta(minutes=30):
        raise ValueError('US collection outside original slot window')
    indices = get(INDEX_URL)
    if indices.get('isSuccess') is not True:
        raise ValueError('US session evidence unavailable')
    anchors = [i for i in indices['result'] if i.get('id') in {'.DJI', '.IXIC'}]
    if len(anchors) != 2 or any(i.get('marketStatus') != 'CLOSE' for i in anchors):
        raise ValueError('US regular session has not closed')
    session_dates = {stamp(i['localTradedAt']).astimezone(NY).date() for i in anchors}
    if len(session_dates) != 1 or any(stamp(i['localTradedAt']) > checked for i in anchors):
        raise ValueError('inconsistent or future US session evidence')
    session = session_dates.pop()
    if not dt.timedelta(0) <= checked.astimezone(NY).date() - session <= dt.timedelta(days=4):
        raise ValueError('US session evidence too old')
    stocks, excluded, pages, seen = [], [], [], set()
    previous = Decimal('Infinity')
    for page in range(1, 5):
        url = rank_url(page)
        body = get(url)
        result = body.get('result', {})
        rows = result.get('stocks')
        if (body.get('isSuccess') is not True or result.get('marketStatus') != 'CLOSE'
                or result.get('page') != page or not isinstance(rows, list) or not rows):
            raise ValueError('USD turnover ranking unavailable or not regular-session close')
        pages.append(url)
        # Read official classification and regular-session timestamp separately.
        for start in range(0, len(rows), 10):
            chunk = rows[start:start+10]
            candidates = [r for r in chunk if r.get('stockEndType') == 'stock']
            with ThreadPoolExecutor(max_workers=6) as pool:
                details = list(pool.map(lambda r: get(basic_url(r['id'])), candidates))
            detail_map = {r['id']: d for r, d in zip(candidates, details)}
            for row in chunk:
                code = row['id']
                amount = number(row.get('accumulatedTradingValue'))
                if code in seen or amount > previous or amount <= 0:
                    raise ValueError('ranking duplicate, unordered or invalid dollar turnover')
                seen.add(code)
                previous = amount
                if row.get('stockEndType') != 'stock':
                    excluded.append({'id': code, 'reason': 'not_common_stock_or_ADR'})
                    continue
                detail = detail_map[code]
                classification = detail.get('stockCodeClassificationType')
                if not classification:
                    raise ValueError('missing security classification: ' + code)
                if type(detail.get('isEtf')) is not bool:
                    raise ValueError('missing ETF classification: ' + code)
                if classification not in SECURITY_TYPES or detail.get('isEtf') is not False:
                    excluded.append({'id': code, 'securityType': classification, 'reason': 'excluded_security_type'})
                    continue
                observed = stamp(detail['localTradedAt'])
                exchange = detail.get('stockExchangeType', {}).get('name')
                if (detail.get('reutersCode') != code or detail.get('marketStatus') != 'CLOSE'
                    or row.get('marketStatus') != 'CLOSE' or exchange not in EXCHANGES
                    or row.get('currencyType') != 'USD' or detail.get('currencyType', {}).get('name') != 'USD'
                    or observed.astimezone(NY).date() != session or observed > checked
                    or number(row['fluctuationsRatio']) != number(detail['fluctuationsRatio'])):
                    raise ValueError('regular-session identity/date/currency/return mismatch: ' + code)
                stocks.append({'id': code, 'symbol': detail['symbolCode'], 'name': detail['stockName'],
                    'securityType': classification, 'exchange': exchange, 'currency': 'USD',
                    'tradeAmountUsd': float(amount), 'changeRate': float(number(detail['fluctuationsRatio'])),
                    'sessionDate': session.isoformat(), 'observedAt': observed.isoformat(),
                    'industry': detail.get('industryCodeType', {}).get('industryGroupKor'),
                    'rankingSourceUrl': url, 'classificationSourceUrl': basic_url(code), 'rank': len(stocks)+1})
                if len(stocks) == 50:
                    result = {'schemaVersion': 1, 'state': 'collected', 'publishable': not probe,
                        'releaseAt': release.isoformat(), 'collectedAt': dt.datetime.now(KST).isoformat() if now is None else checked.isoformat(),
                        'sessionDate': session.isoformat(), 'sessionSourceUrl': INDEX_URL,
                        'sessionEvidence': anchors, 'rankingSourceUrls': pages, 'sourceUrl': PAGE,
                        'currency': 'USD', 'turnoverMethod': 'provider_reported_regular_session_turnover',
                        'scope': 'provider_US_NASDAQ_NYSE_AMEX_common_and_ADR',
                        'stocks': stocks, 'excluded': excluded, 'editorialReviewCompleted': False}
                    validate_snapshot(result)
                    return result
    raise ValueError('fewer than 50 eligible securities within bounded ranking pages')


def validate_snapshot(snapshot):
    if (snapshot.get('state') != 'collected' or snapshot.get('currency') != 'USD'
            or snapshot.get('turnoverMethod') != 'provider_reported_regular_session_turnover'):
        raise ValueError('verified USD turnover snapshot required')
    stocks = snapshot.get('stocks', [])
    if len(stocks) != 50 or len({s['id'] for s in stocks}) != 50:
        raise ValueError('exactly 50 unique eligible stocks required')
    previous = Decimal('Infinity')
    checked = stamp(snapshot['collectedAt'])
    session = dt.date.fromisoformat(snapshot['sessionDate'])
    release = stamp(snapshot['releaseAt']).astimezone(KST)
    anchors = snapshot.get('sessionEvidence', [])
    if (not enabled(release) or release.weekday() >= 5 or type(snapshot.get('publishable')) is not bool
        or {i.get('id') for i in anchors} != {'.DJI', '.IXIC'} or len(anchors) != 2
        or any(i.get('marketStatus') != 'CLOSE' or stamp(i['localTradedAt']).astimezone(NY).date() != session
               or stamp(i['localTradedAt']) > checked for i in anchors)
        or not dt.timedelta(0) <= checked.astimezone(NY).date()-session <= dt.timedelta(days=4)):
        raise ValueError('closed latest US session evidence required')
    if snapshot['publishable'] and not release-dt.timedelta(minutes=30) <= checked <= release+dt.timedelta(minutes=30):
        raise ValueError('source collection outside original edition window')
    for rank, stock in enumerate(stocks, 1):
        amount, change = number(stock['tradeAmountUsd']), number(stock['changeRate'])
        if (stock['rank'] != rank or stock['securityType'] not in SECURITY_TYPES
            or stock['currency'] != 'USD' or stock['exchange'] not in EXCHANGES
            or amount <= 0 or amount > previous or change < -100
            or stock['sessionDate'] != session.isoformat()
            or stamp(stock['observedAt']).astimezone(NY).date() != session
            or stamp(stock['observedAt']) > checked
            or not all(https(stock[k]) for k in ('rankingSourceUrl', 'classificationSourceUrl'))):
            raise ValueError('invalid top-50 stock or mixed session')
        previous = amount
    if (not https(snapshot.get('sessionSourceUrl')) or not https(snapshot.get('sourceUrl'))
            or not snapshot.get('rankingSourceUrls') or not all(https(u) for u in snapshot['rankingSourceUrls'])):
        raise ValueError('ranking and session evidence URLs required')


def aggregate(snapshot, review, cutoff, source_cutoff=None):
    validate_snapshot(snapshot)
    rows = {s['id']: s for s in snapshot['stocks']}
    if (review.get('sessionDate') != snapshot['sessionDate'] or
        not cutoff-dt.timedelta(minutes=15) <= stamp(review['reviewedAt']) <= cutoff):
        raise ValueError('current theme review for same US session required')
    seen, theme_ids, themes = set(), set(), []
    for group in review.get('groups', []):
        ident, label, members = group['id'], group['name'], group['members']
        if not ident or ident in theme_ids or not label.strip() or not members:
            raise ValueError('unique named nonempty theme required')
        theme_ids.add(ident)
        for member in members:
            if member['id'] not in rows or member['id'] in seen or not https(member['classificationSourceUrl']):
                raise ValueError('each top-50 stock must belong to exactly one evidenced theme')
            seen.add(member['id'])
        selected = [rows[m['id']] for m in members]
        total = sum(number(s['tradeAmountUsd']) for s in selected)
        rate = sum(number(s['changeRate'])*number(s['tradeAmountUsd']) for s in selected)/total
        reason = group.get('reason')
        if reason is not None:
            if (not reason.get('summary', '').strip() or not https(reason.get('sourceUrl'))
                or stamp(reason['publishedAt']) > (source_cutoff or cutoff)
                or reason.get('causality') not in {'source_attributed', 'related_fact_only'}):
                raise ValueError('verified factual theme material required')
        themes.append({'id': ident, 'name': label, 'weightedChangeRate': float(rate.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)),
            'tradeAmountUsd': float(total), 'stocks': sorted(selected, key=lambda s: (-number(s['tradeAmountUsd']), s['id'])), 'reason': reason})
    if seen != set(rows):
        raise ValueError('theme review does not cover all 50 stocks; do not claim strongest themes')
    return sorted((t for t in themes if t['weightedChangeRate'] > 0),
                  key=lambda t: (-number(t['weightedChangeRate']), -number(t['tradeAmountUsd']), t['id']))[:3]


def build_report(record, review, release_at, as_of):
    release, cutoff = stamp(release_at).astimezone(KST), stamp(as_of)
    if not enabled(release):
        raise ValueError('US themes only belong to 06:40')
    if record.get('releaseAt') != release.isoformat():
        raise ValueError('US source record belongs to another edition')
    source_checked = record.get('collectedAt') or record.get('checkedAt')
    if not source_checked or not cutoff-dt.timedelta(minutes=30) <= stamp(source_checked) <= cutoff:
        raise ValueError('fresh source status timestamp required')
    if record.get('state') == 'collected' and record.get('publishable') is not True:
        raise ValueError('probe snapshot cannot be used for publication')
    if record.get('state') != 'collected' or not review:
        return {'state': 'unavailable', 'releaseAt': release.isoformat(), 'sourceUrl': PAGE,
            'reason': '테마 분류·근거 검증 미완료' if record.get('state') == 'collected' else '거래대금·종목 분류·정규장 자료 수집 실패',
            'sourceState': record.get('state'), 'sourceCheckedAt': source_checked,
            'themes': []}
    if record.get('publishable') is not True or not cutoff-dt.timedelta(minutes=30) <= stamp(record['collectedAt']) <= cutoff:
        raise ValueError('probe, stale or future source snapshot cannot be published')
    themes = aggregate(record, review, cutoff, release)
    return {'state': 'ready', 'releaseAt': release.isoformat(), 'sourceUrl': PAGE, 'sessionDate': record['sessionDate'],
            'snapshot': record, 'review': review, 'themes': themes}


def card(report, release, as_of):
    if report['state'] == 'ready':
        lines = ['미국 정규장 ' + report['sessionDate'] + ' 마감 · 달러 거래대금 상위 50종목 기준']
        for index, theme in enumerate(report['themes'], 1):
            lines.append('\n' + str(index) + '. ' + theme['name'] + ' ' + format(theme['weightedChangeRate'], '+.2f') + '%')
            lines.append(' · '.join(s['symbol'] + ' ' + format(s['changeRate'], '+.2f') + '%' for s in theme['stocks']))
            reason = theme.get('reason')
            lines.append(('상승 재료: ' if reason and reason['causality'] == 'source_attributed' else '관련 확인 사실: ')
                         + reason['summary'] if reason else '확인된 상승 재료 없음')
        if not report['themes']:
            lines.append('검증된 테마 중 가중평균 등락률이 양수인 테마가 없습니다.')
        title = '미국 거래대금 상위 50종목 · 강한 테마 최대 3개'
        symbols = [s['symbol'] for t in report['themes'] for s in t['stocks']]
        published = max(stamp(s['observedAt']) for s in report['snapshot']['stocks']).isoformat()
    else:
        title, lines, symbols, published = '미국 강한 테마 · 미집계', [report['reason']], [], as_of.isoformat()
        # An unavailable state is an operational notice, not historical market news.
        published = as_of.isoformat()
    return {'id': 'us-themes-' + release.strftime('%Y%m%d'), 'role': ROLE, 'title': title, 'summary': '\n'.join(lines),
        'sourceName': 'Npay 증권·검증된 테마 분류' if report['state'] == 'ready' else 'Market Flow 집계 상태', 'sourceUrl': PAGE, 'reviewSourceUrl': PAGE,
        'publishedAt': published, 'reviewedAt': as_of.isoformat(), 'reviewNote': 'US 테마 근거는 usThemeReport에 보존. 시간외·ETF·ETN·우선주 제외.',
        'validUntil': (release+dt.timedelta(hours=1)).isoformat(), 'impactRank': 1,
        'kind': 'news', 'category': '미국증시', 'region': 'foreign', 'relatedStocks': symbols}


def attach(payload, record, review=None):
    result = copy.deepcopy(payload)
    release, cutoff = stamp(payload['releaseAt']).astimezone(KST), stamp(payload['asOf'])
    report = build_report(record, review, payload['releaseAt'], payload['asOf'])
    original = [i for i in result['items'] if i.get('role') != ROLE]
    if any(i.get('region') not in {'foreign', 'domestic'} for i in original):
        raise ValueError('do not silently discard unclassified briefing news')
    foreign = [i for i in original if i.get('region') == 'foreign']
    domestic = [i for i in original if i.get('region') == 'domestic']
    report['omittedForeignItemIds'] = [i['id'] for i in foreign[9:]]
    result['usThemeReport'] = report
    result['items'] = [card(report, release, cutoff)] + foreign[:9] + domestic
    for rank, item in enumerate(result['items'], 1): item['impactRank'] = rank
    return result


def validate_block(payload):
    release, cutoff = stamp(payload['releaseAt']).astimezone(KST), stamp(payload['asOf'])
    cards = [i for i in payload['items'] if i.get('role') == ROLE or i.get('id', '').startswith('us-themes-')]
    report = payload.get('usThemeReport')
    required = enabled(release) and release.date() >= EFFECTIVE
    if not enabled(release):
        if cards or report is not None:
            raise ValueError('US theme summary forbidden outside 06:40')
        return
    if not required and report is None and not cards:
        return
    if not isinstance(report, dict) or len(cards) != 1 or payload['items'][0] != cards[0]:
        raise ValueError('06:40 requires a first-position US theme report or explicit unavailable notice')
    if report.get('releaseAt') != release.isoformat() or not https(report.get('sourceUrl')):
        raise ValueError('invalid US theme report edition or source')
    if report.get('state') == 'ready':
        expected = build_report(report['snapshot'], report['review'], payload['releaseAt'], payload['asOf'])
        if report.get('themes') != expected['themes'] or report.get('sessionDate') != expected['sessionDate']:
            raise ValueError('US theme ranking/score does not match the reviewed top 50')
    elif report.get('state') != 'unavailable' or report.get('themes') != [] or not report.get('reason', '').strip():
        raise ValueError('invalid unavailable US theme notice')
    elif not cutoff-dt.timedelta(minutes=30) <= stamp(report['sourceCheckedAt']) <= cutoff:
        raise ValueError('unavailable notice must use actual current source-check time')
    if cards[0] != card(report, release, cutoff):
        raise ValueError('US theme summary text/order must match verified calculations')


if __name__ == '__main__':
    # Compose only; the ordinary prepare_feed validator and publisher still gate release.
    draft_path, source_path, review_path, output_path = sys.argv[1:]
    draft, source = (json.loads(pathlib.Path(p).read_text()) for p in (draft_path, source_path))
    review = None if review_path == '-' else json.loads(pathlib.Path(review_path).read_text())
    pathlib.Path(output_path).write_text(json.dumps(attach(draft, source, review), ensure_ascii=False, indent=2)+'\n')
