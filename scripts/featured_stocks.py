"""Market Flow featured stocks: snapshot, reviewed themes, validation and archive.

No quote or causal explanation is invented when a source is unavailable.
All amounts are KRW, rates are percentage points (5.0 means +5%).
"""
import argparse
import datetime as dt
import decimal
import json
import pathlib
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse
from source_http import CollectionFetch, json_response
from featured_strength import active as strength_active, analyze, verify_analysis

KST = dt.timezone(dt.timedelta(hours=9))
SLOTS = ('09:40', '11:40', '13:40', '15:40', '20:10')
BASE = 'https://stock.naver.com/api/domestic/'
NXT_ELIGIBILITY_URL = 'https://nextrade.co.kr/brdinfoTime/brdinfoTimeList.do'
NXT_ELIGIBILITY_PAGE = 'https://nextrade.co.kr/menu/marketData/menuList.do'
D = decimal.Decimal


def stamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone required')
    return parsed.astimezone(KST)


def https(value):
    u = urlparse(value if isinstance(value, str) else '')
    return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password


def number(value):
    n = D(str(value))
    if not n.is_finite():
        raise ValueError('finite number required')
    return n


def get(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'MarketFlow/1.0', 'Accept': 'application/json'})
    return json_response(request)


def get_nxt_eligibility():
    # The official site's grid uses POST and labels this the full tradable list.
    request = urllib.request.Request(NXT_ELIGIBILITY_URL, data=b'pageIndex=1&pageUnit=5000',
        headers={'User-Agent': 'MarketFlow/1.0',
                 'Referer': NXT_ELIGIBILITY_PAGE})
    return json_response(request)


def official_zero_nxt(candidates, known_nxt, body, checked):
    """Prove non-eligibility from a complete, dated official list, never a 404."""
    rows = body.get('brdinfoTimeList', [])
    total = body.get('totalCnt')
    if type(total) is not int or total < 100 or len(rows) != total or body.get('records') != total or body.get('total') != 1:
        raise ValueError('NXT official eligibility list is incomplete')
    observed = dt.datetime.strptime(body['setTime'], '%Y-%m-%d %H:%M').replace(tzinfo=KST)
    if observed.date() != checked.date() or not dt.timedelta(0) <= checked - observed <= dt.timedelta(minutes=30):
        raise ValueError('NXT official eligibility list is stale or future')
    codes = set()
    for row in rows:
        code = row.get('isuSrdCd', '')
        if len(code) == 7 and code.startswith('A'):
            code = code[1:]
        if (not re.fullmatch(r'[0-9A-Z]{6}', code) or code in codes
                or row.get('aggDd') != checked.strftime('%Y%m%d')
                or row.get('nowDd') != checked.strftime('%Y%m%d')):
            raise ValueError('NXT official eligibility identity/date mismatch')
        codes.add(code)
    if not set(known_nxt).issubset(codes):
        raise ValueError('NXT official eligibility contradicts observed trading')
    return {code: {'code': code, 'sourceUrl': NXT_ELIGIBILITY_PAGE, 'requestUrl': NXT_ELIGIBILITY_URL,
        'requestMethod': 'POST', 'requestBody': 'pageIndex=1&pageUnit=5000',
        'checkedAt': checked.isoformat(), 'eligibilityObservedAt': observed.isoformat(),
        'officialEligibleCount': total,
        'reason': checked.date().isoformat() + ' NXT 공식 거래대상 전체 ' + str(total)
                  + '종목 목록에 ' + code + ' 미포함; NXT 비거래를 별도 확인.'}
        for code in candidates if code not in codes}


def weighted(stocks):
    total = sum(s['integratedTradeAmount'] for s in stocks)
    if total <= 0:
        raise ValueError('positive theme turnover required')
    return float((sum(number(s['changeRate']) * s['integratedTradeAmount'] for s in stocks) / total)
                 .quantize(D('0.000001'), rounding=decimal.ROUND_HALF_UP))


def list_url(market):
    return BASE + 'market/stock/default?marketType=ALL&orderType=priceTop&startIdx=0&pageSize=5000&tradeType=' + market


def collect(release, evidence, fetch=get, now=None, eligibility_fetch=get_nxt_eligibility, trace=None, probe=False, full_nxt=False):
    """Use complete KRX universe + NXT top-100 and fill any possible challenger.

    A missing NXT detail is NOT evidence for zero. Only independently verified
    zero-NXT records supplied by the researcher can establish that value.
    """
    started = now or dt.datetime.now(KST)
    target = stamp(release)
    if target.strftime('%H:%M') not in SLOTS or target.weekday() >= 5:
        raise ValueError('invalid featured-stocks release slot')
    if not probe and not target - dt.timedelta(minutes=20) <= started <= target + dt.timedelta(minutes=20):
        raise ValueError('collection outside original edition window')
    if evidence.get('tradingDayVerified') is not True or not https(evidence.get('calendarSourceUrl')):
        raise ValueError('verified KRX trading-day evidence required')
    if evidence.get('date') != target.date().isoformat():
        raise ValueError('calendar evidence must be for this KST date')
    cached = CollectionFetch(fetch)
    fetch = cached
    diagnostics = []
    def report(stage, **values):
        event = {'stage': stage, 'checkedAt': (now or dt.datetime.now(KST)).isoformat(), **values}
        diagnostics.append(event)
        if trace: trace(event)
    cached.prime([list_url(m) for m in ('KRX', 'NXT')])
    records = []
    lists = {}
    for market in ('KRX', 'NXT'):
        url = list_url(market)
        rows = fetch(url)
        if not isinstance(rows, list) or not rows or (market == 'KRX' and len(rows) >= 5000):
            raise ValueError('empty or changed Naver response: ' + market)
        stocks = [x for x in rows if x.get('type') == 'ST']
        if len({x['itemcode'] for x in stocks}) != len(stocks):
            raise ValueError('duplicate ranking identity: ' + market)
        if any(not re.fullmatch(r'[0-9A-Z]{6}', x['itemcode']) or
               not re.fullmatch(r'\d+', str(x.get('tradeAmount', ''))) for x in stocks):
            raise ValueError('invalid ranking identity/amount: ' + market)
        lists[market] = {x['itemcode']: x for x in stocks}
        report('ranking_received', market=market, rows=len(rows), stocks=len(stocks), sourceUrl=url)
        records.append({'market': market, 'sourceUrl': url,
                        'retrievedAt': (now or cached.times[url].astimezone(KST)).isoformat()})
    krx, nxt = lists['KRX'], lists['NXT']
    if len(krx) < 1000 or len(nxt) < 100:
        raise ValueError('insufficient ranking universe; refusing partial top 50')
    if any(c not in krx for c in nxt):
        raise ValueError('NXT stock absent from KRX universe')
    # The endpoint truncates NXT ranking to 100. The smallest returned amount
    # bounds every omitted stock; list ordering and nonnegative amounts checked.
    nxt_values = [int(x['tradeAmount']) for x in nxt.values()]
    zero = {}
    inversions = [{'previousCode': codes[i-1], 'code': codes[i], 'previousAmount': nxt_values[i-1], 'amount': nxt_values[i]}
                  for codes in [list(nxt)] for i in range(1, len(codes)) if nxt_values[i] > nxt_values[i-1]]
    if inversions or full_nxt:
        # Sorting a truncated top-100 list cannot prove the omitted-stock bound.
        # Verify the complete official eligible universe and read exact NXT values.
        report('nxt_order_inversion' if inversions else 'nxt_complete_scan_requested', count=len(inversions), examples=inversions[:10], fallback='complete_official_universe')
        official = eligibility_fetch()
        checked = now or dt.datetime.now(KST)
        zero.update(official_zero_nxt(list(krx), nxt, official, checked))
        eligible = {r['isuSrdCd'].removeprefix('A') for r in official['brdinfoTimeList']} & set(krx)
        if len(eligible) > 2000:
            raise ValueError('official NXT universe exceeds bounded full-scan capacity')
        report('nxt_full_scan_started', eligibleCount=len(eligible), officialObservedAt=official['setTime'])
        complete = {}
        for start in range(0, len(eligible), 60):
            codes = sorted(eligible)[start:start+60]
            cached.prime([BASE+'detail/'+c+'/detail?codeType=NXT' for c in codes])
            for code in codes:
                url = BASE+'detail/'+code+'/detail?codeType=NXT'
                try:
                    detail = fetch(url)
                except urllib.error.HTTPError as error:
                    raise ValueError('NXT official eligible quote unavailable (404 is not zero): '+code) from error
                observed = dt.datetime.strptime(detail['tradeTime'], '%Y%m%d%H%M%S').replace(tzinfo=KST)
                if (detail.get('itemcode') != code or not re.fullmatch(r'\d+', str(detail.get('tradeAmount', '')))
                    or observed.date() != target.date() or observed > (now or dt.datetime.now(KST))+dt.timedelta(seconds=30)):
                    raise ValueError('NXT complete universe quote identity/date/amount mismatch: '+code)
                complete[code] = detail
                records.append({'market': 'NXT', 'code': code, 'sourceUrl': url,
                                'retrievedAt': (now or cached.times[url].astimezone(KST)).isoformat()})
            report('nxt_full_scan_progress', completed=len(complete), eligibleCount=len(eligible))
            if (now or dt.datetime.now(KST))-started > dt.timedelta(minutes=5):
                raise ValueError('collection skew exceeds five minutes; collect again')
        nxt = complete
        upper = 0  # Every eligible ST value is exact; every other ST has official proof.
        records.append({'market': 'NXT', 'sourceUrl': NXT_ELIGIBILITY_PAGE, 'requestUrl': NXT_ELIGIBILITY_URL,
            'requestMethod': 'POST', 'requestBody': 'pageIndex=1&pageUnit=5000', 'retrievedAt': checked.isoformat(),
            'kind': 'complete_official_eligibility', 'eligibilityObservedAt': official['setTime'],
            'officialEligibleCount': official['totalCnt']})
        report('nxt_full_scan_verified', exactQuotes=len(complete), officialNonEligible=len(zero))
    else:
        upper = min(nxt_values)
        report('nxt_truncated_ranking_verified', rows=len(nxt), omittedAmountUpperBound=upper)
    for z in evidence.get('zeroNxt', []):
        if not https(z.get('sourceUrl')) or stamp(z['checkedAt']).date() != target.date() or not z.get('reason'):
            raise ValueError('zero NXT requires dated explicit non-trading evidence')
        zero[z['code']] = z
    known = {c: int(x['tradeAmount']) + int(nxt.get(c, {}).get('tradeAmount', 0)) for c, x in krx.items()}
    cutoff = sorted(known.values(), reverse=True)[49]
    unresolved = []
    challengers = [c for c, row in krx.items() if c not in nxt and c not in zero and int(row['tradeAmount']) + upper >= cutoff]
    cached.prime([BASE + 'detail/' + c + '/detail?codeType=NXT' for c in challengers])
    for code, row in krx.items():
        if code in nxt or code in zero or int(row['tradeAmount']) + upper < cutoff:
            continue
        url = BASE + 'detail/' + code + '/detail?codeType=NXT'
        try:
            detail = fetch(url)
            if detail.get('itemcode') != code or detail.get('tradeAmount') is None:
                raise ValueError('NXT detail shape changed')
            nxt[code] = detail
            known[code] = int(row['tradeAmount']) + int(detail['tradeAmount'])
            records.append({'market': 'NXT', 'code': code, 'sourceUrl': url,
                            'retrievedAt': (now or cached.times[url].astimezone(KST)).isoformat()})
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            unresolved.append(code)
    ordered = sorted(known, key=lambda c: (-known[c], c))[:50]
    cutoff = known[ordered[-1]]
    uncertain = [c for c in unresolved if int(krx[c]['tradeAmount']) + upper >= cutoff]
    if uncertain:
        try:
            checked = now or dt.datetime.now(KST)
            official = eligibility_fetch()
            confirmed_zero = official_zero_nxt(uncertain, nxt, official, checked)
            zero.update(confirmed_zero)
            records.append({'market': 'NXT', 'sourceUrl': NXT_ELIGIBILITY_PAGE, 'requestUrl': NXT_ELIGIBILITY_URL,
                'requestMethod': 'POST', 'requestBody': 'pageIndex=1&pageUnit=5000',
                'retrievedAt': checked.isoformat(), 'kind': 'official_eligibility',
                'eligibilityObservedAt': official['setTime'],
                'officialEligibleCount': official['totalCnt']})
            uncertain = [c for c in uncertain if c not in confirmed_zero]
        except (ValueError, KeyError, TypeError, urllib.error.URLError) as error:
            raise ValueError('NXT turnover unverified (404 is not zero); official eligibility unavailable: ' + str(error)) from error
    if uncertain:
        raise ValueError('NXT turnover unverified (404 is not zero): ' + ','.join(uncertain))
    cached.prime([BASE + 'detail/' + c + '/detail?codeType=' + m for c in ordered
                  for m in (('KRX', 'NXT') if c in nxt else ('KRX',))])
    stocks = []
    for rank, code in enumerate(ordered, 1):
        k = krx[code]
        n = nxt.get(code)
        if n is None and code not in zero:
            raise ValueError('selected stock lacks exact NXT amount: ' + code)
        # Independently fetch timestamped market details for the selected names.
        quotes = {}
        for market in ('KRX', 'NXT') if n is not None else ('KRX',):
            url = BASE + 'detail/' + code + '/detail?codeType=' + market
            q = fetch(url)
            observed = dt.datetime.strptime(q['tradeTime'], '%Y%m%d%H%M%S').replace(tzinfo=KST)
            checked = now or dt.datetime.now(KST)
            if observed.date() != target.date() or observed > checked + dt.timedelta(seconds=30):
                raise ValueError('quote date/future timestamp mismatch: ' + code)
            # After the regular close, KRX closing observations remain historical.
            close = dt.datetime.combine(target.date(), dt.time(15, 30), KST)
            allowed_close = market == 'KRX' and checked >= close and observed >= close
            if not allowed_close and checked - observed > dt.timedelta(minutes=15):
                raise ValueError('stale observation: ' + code + '/' + market)
            quotes[market] = {'observedAt': observed.isoformat(), 'sourceUrl': url}
        stocks.append({'code': code, 'name': k['itemname'], 'turnoverRank': rank,
                       'krxTradeAmount': int(k['tradeAmount']),
                       'nxtTradeAmount': int(n['tradeAmount']) if n else 0,
                       'integratedTradeAmount': known[code], 'changeRate': float(number(k['prevChangeRate'])),
                       'rateMarket': 'KRX', 'quotes': quotes,
                       'zeroNxtEvidence': zero.get(code),
                       **({'marketCapKrw': int(k['marketSum'])} if k.get('marketSum', '').isdigit() else {}),
                       **({'isUpperLimit': k['nowPrice'] == k['upperLimitPrice']}
                          if k.get('nowPrice', '').isdigit() and k.get('upperLimitPrice', '').isdigit() else {})})
    ended = now or dt.datetime.now(KST)
    if ended - started > dt.timedelta(minutes=5):
        raise ValueError('collection skew exceeds five minutes; collect again')
    # Quotes validate contemporaneity; amounts/rates above remain the actual
    # list observations, with their own retrieval times, not relabelled details.
    report('top_fifty_verified', stockCount=50, requestCount=len(cached.values)+len(cached.errors))
    return {'schemaVersion': 1, 'asOf': ended.isoformat(), 'collectionStartedAt': started.isoformat(),
            'releaseAt': target.isoformat(), 'tradingDayVerified': True,
            'calendarSourceUrl': evidence['calendarSourceUrl'], 'sourceName': '네이버 증권',
            'amountUnit': 'KRW', 'rateBasis': 'KRX_PREVIOUS_CLOSE',
            'serverRetentionCalendarDays': 3, 'appVisibleCalendarDays': 2,
            'sourceRecords': records, 'stocks': stocks,
            'byTurnover': ordered,
            'byChangeRate': [s['code'] for s in sorted(stocks, key=lambda s: (-s['changeRate'], -s['integratedTradeAmount'], s['code']))],
            'themes': [], 'unclassified': list(ordered), 'collectionDiagnostics': diagnostics,
            'probeOnly': probe}


def enrich(snapshot, review):
    result = dict(snapshot)
    by_code = {s['code']: s for s in snapshot['stocks']}
    used, themes = set(), []
    for entry in review['themes']:
        codes = entry['stockCodes']
        if not codes or len(codes) != len(set(codes)) or any(c not in by_code or c in used for c in codes):
            raise ValueError('theme membership missing/unknown/duplicated')
        used.update(codes)
        theme = dict(entry)
        members = [by_code[c] for c in codes]
        theme['stockCodes'] = [s['code'] for s in sorted(members, key=lambda s: (-s['changeRate'], -s['integratedTradeAmount'], s['code']))]
        theme['weightedChangeRate'] = weighted(members)
        theme['integratedTradeAmount'] = sum(s['integratedTradeAmount'] for s in members)
        themes.append(theme)
    result['themes'] = sorted(themes, key=lambda t: (-t['weightedChangeRate'], -t['integratedTradeAmount'], t['id']))
    result['unclassified'] = [c for c in result['byChangeRate'] if c not in used]
    result['reviewedAt'] = review['reviewedAt']
    if strength_active(result):
        result.update(analyze(result, themes))
    return validate(result)


def validate(p):
    if p.get('probeOnly') is True:
        raise ValueError('collection probe is not publishable')
    release, as_of = stamp(p['releaseAt']), stamp(p['asOf'])
    if p.get('schemaVersion') != 1 or release.strftime('%H:%M') not in SLOTS or release.weekday() >= 5:
        raise ValueError('invalid featured-stocks edition')
    if p.get('tradingDayVerified') is not True or not https(p.get('calendarSourceUrl')):
        raise ValueError('trading day evidence required')
    if not release - dt.timedelta(minutes=20) <= as_of <= release + dt.timedelta(minutes=20):
        raise ValueError('snapshot outside edition window')
    if p.get('amountUnit') != 'KRW' or p.get('rateBasis') != 'KRX_PREVIOUS_CLOSE':
        raise ValueError('unknown amount or rate basis')
    started = stamp(p['collectionStartedAt'])
    if not dt.timedelta(0) <= as_of - started <= dt.timedelta(minutes=5):
        raise ValueError('invalid collection window')
    sources = p.get('sourceRecords', [])
    if not {'KRX', 'NXT'}.issubset({s['market'] for s in sources}):
        raise ValueError('both market source records required')
    if any(not https(s.get('sourceUrl')) or not started <= stamp(s['retrievedAt']) <= as_of for s in sources):
        raise ValueError('invalid source retrieval time')
    stocks = p['stocks']
    if len(stocks) != 50 or len({s['code'] for s in stocks}) != 50:
        raise ValueError('exactly 50 unique stocks required')
    expected = sorted(stocks, key=lambda s: (-s['integratedTradeAmount'], s['code']))
    if p['byTurnover'] != [s['code'] for s in expected]:
        raise ValueError('incorrect turnover order')
    if p['byChangeRate'] != [s['code'] for s in sorted(stocks, key=lambda s: (-s['changeRate'], -s['integratedTradeAmount'], s['code']))]:
        raise ValueError('incorrect rate order')
    for rank, s in enumerate(expected, 1):
        if s['turnoverRank'] != rank or not re.fullmatch(r'[0-9A-Z]{6}', s['code']) or not s['name']:
            raise ValueError('invalid stock identity/rank')
        for key in ('krxTradeAmount', 'nxtTradeAmount', 'integratedTradeAmount'):
            if type(s[key]) is not int or s[key] < 0:
                raise ValueError('invalid turnover')
        if s['integratedTradeAmount'] != s['krxTradeAmount'] + s['nxtTradeAmount']:
            raise ValueError('turnover sum mismatch')
        number(s['changeRate'])
        if 'marketCapKrw' in s and (type(s['marketCapKrw']) is not int or s['marketCapKrw'] < 0):
            raise ValueError('invalid observed market cap')
        if 'isUpperLimit' in s and type(s['isUpperLimit']) is not bool:
            raise ValueError('invalid observed limit-up flag')
        if s.get('rateMarket') != 'KRX':
            raise ValueError('mixed rate basis')
        for market in ('KRX', 'NXT'):
            q = s['quotes'].get(market)
            if q is None:
                z = s.get('zeroNxtEvidence')
                if (market != 'NXT' or s['nxtTradeAmount'] != 0 or not z or not https(z.get('sourceUrl'))
                        or z.get('code') != s['code'] or not z.get('reason')
                        or stamp(z['checkedAt']).date() != release.date() or stamp(z['checkedAt']) > as_of):
                    raise ValueError('missing market quote/evidence')
                continue
            observed = stamp(q['observedAt'])
            if not https(q['sourceUrl']) or observed.date() != release.date() or observed > as_of:
                raise ValueError('invalid quote source/time')
            close = dt.datetime.combine(release.date(), dt.time(15, 30), KST)
            if as_of - observed > dt.timedelta(minutes=20) and not (market == 'KRX' and as_of >= close and observed >= close):
                raise ValueError('stale quote')
    reviewed = stamp(p['reviewedAt'])
    if not as_of <= reviewed <= release + dt.timedelta(minutes=20):
        raise ValueError('invalid actual theme review time')
    by_code, used = {s['code']: s for s in stocks}, set()
    ids = set()
    new_selection = strength_active(p)
    if new_selection and p.get('themeSelectionVersion') != 2:
        raise ValueError('theme selection version 2 required for new editions')
    for t in (p.get('themeAssessments', []) if new_selection else p['themes']):
        if not t['id'] or t['id'] in ids or not t['name']:
            raise ValueError('theme identity duplicated/missing')
        ids.add(t['id'])
        codes = t['stockCodes']
        if not codes or len(codes) != len(set(codes)) or any(c not in by_code or c in used for c in codes):
            raise ValueError('invalid theme membership')
        used.update(codes)
        members = [by_code[c] for c in codes]
        if codes != [s['code'] for s in sorted(members, key=lambda s: (-s['changeRate'], -s['integratedTradeAmount'], s['code']))]:
            raise ValueError('incorrect theme member order')
        if abs(number(t['weightedChangeRate']) - number(weighted(members))) > D('0.000001'):
            raise ValueError('weighted rate mismatch')
        if t['integratedTradeAmount'] != sum(s['integratedTradeAmount'] for s in members):
            raise ValueError('theme turnover mismatch')
        evidence = t.get('membershipEvidence', [])
        if len(evidence) != len(codes) or {e['code'] for e in evidence} != set(codes) or any(not https(e.get('sourceUrl')) or not e.get('fact') for e in evidence):
            raise ValueError('verified business/theme relation required for every member')
        reason = t.get('reason')
        if reason is not None:
            if not reason.get('summary') or not https(reason.get('sourceUrl')):
                raise ValueError('reason requires actual source')
            published, checked = stamp(reason['publishedAt']), stamp(reason['checkedAt'])
            if published > reviewed or published.date() != release.date() or not as_of <= checked <= reviewed:
                raise ValueError('reason publication/review time mismatch')
            if reason.get('causality') not in ('source_attributed', 'related_fact_only'):
                raise ValueError('separate reported cause from merely related facts')
    if new_selection:
        verify_analysis(p)
        used = {c for t in p['themes'] for c in t['stockCodes']}
    if not new_selection and p['themes'] != sorted(p['themes'], key=lambda t: (-t['weightedChangeRate'], -t['integratedTradeAmount'], t['id'])):
        raise ValueError('theme order mismatch')
    if len(p['unclassified']) != len(set(p['unclassified'])) or set(p['unclassified']) != set(by_code) - used:
        raise ValueError('all 50 stocks must be accounted for')
    return p


def archive(payload, previous=None):
    release = stamp(payload['releaseAt'])
    date, slot = release.strftime('%Y-%m-%d'), release.strftime('%H:%M')
    if previous and previous['date'] != date:
        raise ValueError('archive date mismatch')
    editions = dict((previous or {}).get('editions', {}))
    editions[slot] = payload
    return {'date': date, 'editions': dict(sorted(editions.items()))}


def retained_dates(dates, today, days):
    return sorted(d for d in dates if today - dt.timedelta(days=days - 1) <= dt.date.fromisoformat(d) <= today)


def write(path, payload):
    dest = pathlib.Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    c = sub.add_parser('collect')
    c.add_argument('--release-at', required=True)
    c.add_argument('--evidence', required=True)
    c.add_argument('--output', required=True)
    s = sub.add_parser('stage')
    s.add_argument('snapshot')
    s.add_argument('review')
    s.add_argument('output')
    v = sub.add_parser('validate')
    v.add_argument('draft')
    args = parser.parse_args()
    read = lambda p: json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
    if args.command == 'collect':
        write(args.output, collect(args.release_at, read(args.evidence)))
    elif args.command == 'stage':
        write(args.output, enrich(read(args.snapshot), read(args.review)))
    else:
        validate(read(args.draft))
    print('Featured-stocks ' + args.command + ' passed')


if __name__ == '__main__':
    main()

