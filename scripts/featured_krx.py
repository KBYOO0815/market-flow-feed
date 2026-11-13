"""Full KRX stock universe -> verified top 100; NXT is not queried or zero-filled."""
import datetime as dt
import re
from featured_stocks import KST, SLOTS, BASE, stamp, https, number, list_url
from source_http import CollectionFetch


def collect_krx(release, evidence, fetch, now=None, trace=None, probe=False):
    started = now or dt.datetime.now(KST)
    target = stamp(release)
    if target.strftime('%H:%M') not in SLOTS or target.weekday() >= 5:
        raise ValueError('invalid featured-stocks release slot')
    if not probe and not target-dt.timedelta(minutes=20) <= started <= target+dt.timedelta(minutes=20):
        raise ValueError('collection outside original edition window')
    if evidence.get('date') != target.date().isoformat() or evidence.get('tradingDayVerified') is not True or not https(evidence.get('calendarSourceUrl')):
        raise ValueError('verified same-day trading evidence required')
    cache = CollectionFetch(fetch)
    diagnostics = []
    def report(stage, **fields):
        event = {'stage':stage,'checkedAt':(now or dt.datetime.now(KST)).isoformat(),**fields}
        diagnostics.append(event)
        if trace: trace(event)
    url = list_url('KRX')
    rows = cache(url)
    if not isinstance(rows,list) or not 1000 <= len(rows) < 5000:
        raise ValueError('incomplete KRX universe; refusing partial top 100')
    stocks = [r for r in rows if r.get('type') == 'ST']
    if len(stocks)<1000 or len({r['itemcode'] for r in stocks}) != len(stocks):
        raise ValueError('incomplete or duplicated KRX stock universe')
    if any(not re.fullmatch(r'[0-9A-Z]{6}',r.get('itemcode','')) or not re.fullmatch(r'\d+',str(r.get('tradeAmount',''))) for r in stocks):
        raise ValueError('invalid KRX identity/amount')
    top = sorted(stocks,key=lambda r:(-int(r['tradeAmount']),r['itemcode']))[:100]
    records = [{'market':'KRX','sourceUrl':url,'retrievedAt':(now or cache.times[url].astimezone(KST)).isoformat()}]
    report('krx_universe_verified',stockUniverseCount=len(stocks),selectedCount=100,turnoverBasis='KRX')
    urls = [BASE+'detail/'+r['itemcode']+'/detail?codeType=KRX' for r in top]
    cache.prime(urls)
    selected = []
    for rank,(r,url) in enumerate(zip(top,urls),1):
        q = cache(url)
        observed = dt.datetime.strptime(q['tradeTime'],'%Y%m%d%H%M%S').replace(tzinfo=KST)
        checked = now or dt.datetime.now(KST)
        close = dt.datetime.combine(target.date(),dt.time(15,30),KST)
        if (q.get('itemcode') != r['itemcode'] or observed.date() != target.date() or observed > checked
                or (checked-observed > dt.timedelta(minutes=15) and not (checked >= close and observed >= close))):
            raise ValueError('KRX quote identity/date/freshness mismatch: '+r['itemcode'])
        stock = {'code':r['itemcode'],'name':r['itemname'],'turnoverRank':rank,
                 'tradeAmount':int(r['tradeAmount']),'krxTradeAmount':int(r['tradeAmount']),
                 'changeRate':float(number(r['prevChangeRate'])),'rateMarket':'KRX',
                 'quotes':{'KRX':{'observedAt':observed.isoformat(),'sourceUrl':url}}}
        if str(r.get('marketSum','')).isdigit(): stock['marketCapKrw']=int(r['marketSum'])
        if str(r.get('nowPrice','')).isdigit() and str(r.get('upperLimitPrice','')).isdigit():
            stock['isUpperLimit']=int(r['nowPrice']) == int(r['upperLimitPrice'])
        selected.append(stock)
        records.append({'market':'KRX','code':r['itemcode'],'sourceUrl':url,
                        'retrievedAt':(now or cache.times[url].astimezone(KST)).isoformat()})
    ended = now or dt.datetime.now(KST)
    if ended-started > dt.timedelta(minutes=5): raise ValueError('collection skew exceeds five minutes')
    report('top_hundred_verified',stockCount=100,requestCount=len(cache.values),turnoverBasis='KRX')
    return {'schemaVersion':2,'turnoverBasis':'KRX','universeSize':100,'asOf':ended.isoformat(),
            'collectionStartedAt':started.isoformat(),'releaseAt':target.isoformat(),
            'tradingDayVerified':True,'calendarSourceUrl':evidence['calendarSourceUrl'],
            'sourceName':'네이버 증권 KRX','amountUnit':'KRW','rateBasis':'KRX_PREVIOUS_CLOSE',
            'serverRetentionCalendarDays':3,'appVisibleCalendarDays':2,'stocks':selected,
            'sourceRecords':records,'byTurnover':[s['code'] for s in selected],
            'byChangeRate':[s['code'] for s in sorted(selected,key=lambda s:(-s['changeRate'],-s['tradeAmount'],s['code']))],
            'themes':[],'unclassified':[s['code'] for s in selected],
            'collectionDiagnostics':diagnostics,'probeOnly':probe}
