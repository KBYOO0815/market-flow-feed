"""Integrated Top100 contract. All evidence is explicit; incomplete input fails closed."""
import copy
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP
import re
from urllib.parse import urlparse

KST = dt.timezone(dt.timedelta(hours=9))
SLOTS = ('09:40','11:40','13:40','15:40','20:10')
UNKNOWN = '당일 상승 이유 확인 안 됨'


def stamp(s):
    d=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('timezone required')
    return d.astimezone(KST)


def require(ok, message):
    if not ok: raise ValueError(message)


def https(s):
    u=urlparse(s if isinstance(s,str) else '')
    return u.scheme=='https' and bool(u.hostname) and not u.username and not u.password


def num(x):
    require(type(x) in (int,float,str,Decimal),'invalid numeric type')
    d=Decimal(str(x));require(d.is_finite(),'nonfinite number');return d


def money(x):
    require(type(x) is int and x>=0,'nonnegative integer KRW required');return x


def weighted(rows):
    total=sum(money(s['integratedTradeAmount']) for s in rows)
    require(total>0,'positive theme turnover required')
    return float((sum(num(s['changeRate'])*s['integratedTradeAmount'] for s in rows)/total).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP))


def trading(e,date):
    require(e.get('date')==date and e.get('verified') is True,'same-day verified trading evidence required')
    require(e.get('isTradingDay') is True,'KRX closed: skip collection and publication')
    require(https(e.get('sourceUrl')) and e.get('facts'),'official calendar/actual-market facts required')
    require(stamp(e['checkedAt']).date().isoformat()==date,'trading evidence date mismatch')


def eligible(s):
    require(s.get('classificationVerified') is True and https(s.get('classificationSourceUrl')),'security classification unverified: '+str(s.get('code')))
    return s.get('market') in ('KOSPI','KOSDAQ') and s.get('securityType') in ('COMMON','PREFERRED')


def quote(q,date,asof,market):
    require(q.get('market')==market and q.get('tradeDate')==date and q.get('turnoverScope')==market+'_ONLY','market/date/turnover definition mismatch')
    require(https(q.get('sourceUrl')),'quote HTTPS required')
    observed=stamp(q['observedAt']);checked=stamp(q['retrievedAt'])
    require(observed.date().isoformat()==date and observed<=checked<=asof,'quote observation/retrieval invalid')
    require(dt.timedelta(0)<=asof-checked<=dt.timedelta(minutes=5),'quote retrieval stale')
    require(q.get('session') in ('REGULAR_MARKET','REGULAR_CLOSE','NXT_CUMULATIVE','NXT_FINAL'),'unrecognized session')
    money(q['turnover'])


def rank_universe(universe, krx, nxt, coverage, date, asof, slot):
    """Full security master and full market amounts, not a union of top100 lists."""
    require(coverage.get('securityMasterComplete') is True and coverage.get('krxComplete') is True and coverage.get('nxtComplete') is True,'complete market coverage required; truncated ranking is not proof')
    require(coverage.get('date')==date and https(coverage.get('sourceUrl')),'coverage date/source required')
    require(len(universe)==len({s['code'] for s in universe}),'duplicate master identity')
    require(len(krx)==len({s['code'] for s in krx}) and len(nxt)==len({s['code'] for s in nxt}),'duplicate venue quote')
    km={s['code']:s for s in krx};nm={s['code']:s for s in nxt}
    require(all(re.fullmatch(r'[0-9A-Z]{6}',s.get('code','')) and s.get('name') for s in universe),'invalid security identity')
    eligible_codes={s['code'] for s in universe if eligible(s)}
    require(eligible_codes<=set(km),'KRX universe incomplete')
    official=set(coverage.get('nxtEligibleCodes',[]))
    require(official<=set(nm),'NXT eligible quote missing; never zero-fill')
    require(set(nm)<=official,'NXT universe contradicts official eligibility')
    rows=[]
    for s in universe:
        if s['code'] not in eligible_codes: continue
        code=s['code'];k=km[code];n=nm.get(code)
        quote(k,date,asof,'KRX')
        if n: quote(n,date,asof,'NXT')
        if slot=='20:10':
            require(k['session']=='REGULAR_CLOSE' and k.get('closeConfirmed') is True,'20:10 requires verified KRX regular close')
            require(not n or n['session']=='NXT_FINAL' and n.get('closeConfirmed') is True,'20:10 requires actual NXT final total')
        else:
            require(k['session'] in ('REGULAR_MARKET','REGULAR_CLOSE'),'KRX aftermarket price not allowed')
            require(asof-stamp(k['observedAt'])<=dt.timedelta(minutes=15) or k.get('closeConfirmed') is True,'stale KRX quote')
            require(not n or asof-stamp(n['observedAt'])<=dt.timedelta(minutes=15),'stale NXT quote')
        base=k.get('previousRegularClose');price=k.get('price')
        comparison=k.get('comparison',{'eligible':True,'basis':'KRX_PREVIOUS_REGULAR_CLOSE'})
        if comparison.get('eligible'):
            require(comparison.get('basis') in ('KRX_PREVIOUS_REGULAR_CLOSE','OFFICIAL_NEW_LISTING_REFERENCE') and https(k.get('priceSourceUrl')),'verified price comparison required')
            require(num(base)>0 and num(price)>0,'positive base/current price required')
            if comparison['basis']=='OFFICIAL_NEW_LISTING_REFERENCE':require(comparison.get('explanation') and https(comparison.get('sourceUrl')),'listing reference evidence required')
            rate=float(((num(price)/num(base)-1)*100).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP))
        else:
            require(comparison.get('explanation'),'missing comparison explanation');rate=None
        rows.append({**s,'krxTradeAmount':k['turnover'],'nxtTradeAmount':n['turnover'] if n else 0,
            'integratedTradeAmount':k['turnover']+(n['turnover'] if n else 0),'changeRate':rate,'rateMarket':'KRX',
            'previousRegularClose':base,'price':price,'comparison':comparison,'quotes':{'KRX':k,**({'NXT':n} if n else {})},
            **({'zeroNxtEvidence':{'sourceUrl':coverage['sourceUrl'],'tradeDate':date,'reason':'공식 전체 NXT 거래대상 미포함'}} if not n else {})})
    rows.sort(key=lambda s:(-s['integratedTradeAmount'],s['code']))
    require(len(rows)>=100,'fewer than 100 eligible stocks')
    for i,s in enumerate(rows[:100],1):s['turnoverRank']=i
    proof={**copy.deepcopy(coverage),'nxtEligibleCodes':sorted(official & eligible_codes),'method':'full_universe','eligibleCount':len(rows),'cutoffAmount':rows[99]['integratedTradeAmount'],
           'excludedMaxAmount':rows[100]['integratedTradeAmount'] if len(rows)>100 else 0,'allMarketRows':rows}
    return rows[:100],proof


def selected(stocks):
    return sorted([s['code'] for s in stocks if s['comparison'].get('eligible') and num(s['changeRate'])>=4],key=lambda c:next((-num(s['changeRate']),-s['integratedTradeAmount'],c) for s in stocks if s['code']==c))


def reason(r,asof,reviewed,date):
    if r is None:return
    require(r.get('summary') and https(r.get('sourceUrl')) and r.get('facts'),'reason requires actual facts/source')
    require(r.get('causality') in ('source_attributed','related_fact_only'),'unknown causality')
    published=stamp(r['publishedAt']);checked=stamp(r['checkedAt'])
    require(published.date().isoformat()==date and published<=asof<=checked<=reviewed,'reason publication/review chronology invalid')
    require(r.get('verificationStatus')=='confirmed','unverified reason')


def enrich(snapshot,review):
    p=copy.deepcopy(snapshot);p['reviewedAt']=review['reviewedAt'];by={s['code']:s for s in p['stocks']}
    p['selectedStockCodes']=selected(p['stocks']);p['themes']=[]
    for raw in review.get('themes',[]):
        t=copy.deepcopy(raw);members=[by[c] for c in t['stockCodes']]
        t['stockCodes']=sorted(t['stockCodes'],key=lambda c:(-by[c]['changeRate'],-by[c]['integratedTradeAmount'],c))
        t['weightedChangeRate']=weighted(members);t['integratedTradeAmount']=sum(s['integratedTradeAmount'] for s in members)
        p['themes'].append(t)
    p['themes'].sort(key=lambda t:(-t['weightedChangeRate'],-t['integratedTradeAmount'],t['id']))
    assigned={c for t in p['themes'] for c in t['stockCodes']}
    individual={x['code']:x for x in review.get('individualStocks',[])}
    require(len(individual)==len(review.get('individualStocks',[])),'duplicate individual review')
    p['individualStocks']=[individual.get(c,{'code':c,'reason':None}) for c in p['selectedStockCodes'] if c not in assigned]
    require(set(individual)<=set(p['selectedStockCodes'])-assigned,'unexpected/duplicated individual review')
    p['status']={'collection':'success','validation':'success','publication':'pending'}
    return validate(p)


def validate(p):
    require(p.get('schemaVersion')==3 and p.get('turnoverBasis')=='KRX_NXT' and p.get('universeSize')==100,'schema3 combined top100 required')
    require(not p.get('probeOnly'),'probe cannot publish')
    release=stamp(p['releaseAt']);asof=stamp(p['asOf']);reviewed=stamp(p['reviewedAt']);date=release.date().isoformat();slot=release.strftime('%H:%M')
    require(p.get('date')==date and p.get('slot')==slot and slot in SLOTS,'date/slot mismatch')
    require(p.get('amountUnit')=='KRW' and p.get('rateBasis')=='KRX_PREVIOUS_CLOSE','unit/rate basis mismatch')
    require(stamp(p['collectionStartedAt'])<=asof<=reviewed,'actual chronology invalid')
    require(asof.date()==release.date(),'cross-day snapshot forbidden')
    trading(p['tradingDayEvidence'],date)
    proof=p['rankingProof'];rows=proof['allMarketRows']
    rebuilt,check=rank_universe(rows,[s['quotes']['KRX'] for s in rows],[s['quotes']['NXT'] for s in rows if 'NXT' in s['quotes']],proof,date,asof,slot)
    require(p['stocks']==rebuilt and len(p['stocks'])==100,'raw top100 differs from complete-universe proof')
    require(proof['cutoffAmount']==check['cutoffAmount'] and proof['eligibleCount']==check['eligibleCount'],'ranking proof mismatch')
    require(p['selectedStockCodes']==selected(p['stocks']),'all >=4% stocks must be selected exactly')
    by={s['code']:s for s in p['stocks']};used=set();ids=set()
    for t in p['themes']:
        codes=t['stockCodes'];require(len(codes)>=2 and len(set(codes))==len(codes),'theme needs >=2 distinct selected members')
        require(t.get('id') and t['id'] not in ids and t.get('name'),'theme identity');ids.add(t['id'])
        require(set(codes)<=set(p['selectedStockCodes']) and not used.intersection(codes),'theme duplicate/unselected membership');used.update(codes)
        require(abs(num(t['weightedChangeRate'])-num(weighted([by[c] for c in codes])))<=Decimal('.000001'),'weighted rate mismatch')
        require(t['integratedTradeAmount']==sum(by[c]['integratedTradeAmount'] for c in codes),'theme turnover mismatch')
        evidence=t.get('membershipEvidence',[])
        require(len(evidence)==len(codes) and {e['code'] for e in evidence}==set(codes) and all(https(e.get('sourceUrl')) and e.get('fact') for e in evidence),'theme membership source required')
        require(t.get('groupingBasis') in ('industry','shared_catalyst'),'grouping basis required')
        require(t.get('groupingBasis')!='shared_catalyst' or t.get('reason') is not None,'shared catalyst requires verified reason')
        reason(t.get('reason'),asof,reviewed,date)
        for peer in t.get('representativeObservations',[]):
            require(peer.get('code') in by and peer['changeRate']==by[peer['code']]['changeRate'],'representative observation must match raw top100')
        if any(x['changeRate'] is not None and x['changeRate']<=0 for x in t.get('representativeObservations',[])):
            require('부분 강세' in t.get('context',''),'partial strength explanation required')
    require(p['themes']==sorted(p['themes'],key=lambda t:(-t['weightedChangeRate'],-t['integratedTradeAmount'],t['id'])),'theme ordering')
    for x in p['individualStocks']:
        c=x['code'];require(c in p['selectedStockCodes'] and c not in used,'duplicate/unselected individual');used.add(c);reason(x.get('reason'),asof,reviewed,date)
    require(used==set(p['selectedStockCodes']),'selected stock classification incomplete')
    require([x['code'] for x in p['individualStocks']]==[c for c in p['selectedStockCodes'] if c not in {c for t in p['themes'] for c in t['stockCodes']}],'individual rate ordering')
    require(p['status']['collection']=='success' and p['status']['validation']=='success','incomplete collection/validation')
    require(p['status']['publication'] in ('pending','success'),'invalid publication state')
    if p['status']['publication']=='success':require(stamp(p['publishedAt'])>=reviewed,'publication time invalid')
    return p
