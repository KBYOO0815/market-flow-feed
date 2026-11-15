"""Validate/merge the single direct-write feed. No workflow or network publishing.

validate FILE [--today YYYY-MM-DD]
merge CURRENT DRAFT OUTPUT [--today YYYY-MM-DD]
DRAFT: {date,isKrxTradingDay,session,researchState?}. Writer must re-read SHA
before merge and verify the saved JSON using a fresh GitHub read.
"""
import argparse
import copy
import datetime as dt
import json
import math
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

SLOTS = ('06:40', '08:40', '12:40', '19:40')
KST = ZoneInfo('Asia/Seoul')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def timestamp(value):
    require(isinstance(value,str), 'timestamp string required')
    parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    require(parsed.tzinfo is not None, 'timezone required')
    return parsed

def https(url):
    try:
        u=urlsplit(url)
        return u.scheme=='https' and bool(u.hostname) and not u.username and not u.password
    except (TypeError,ValueError):
        return False

def finite(n):
    return isinstance(n,(int,float)) and not isinstance(n,bool) and math.isfinite(n)

def validate_session(s, date, trading, strict=False):
    require(s['slot'] in SLOTS, 'invalid slot')
    require(trading or s['slot'] in ('06:40','19:40'), 'closed-day slot')
    cutoff=timestamp(s['asOf'])
    require(cutoff.astimezone(KST).date()==dt.date.fromisoformat(date),'asOf date mismatch')
    require(cutoff<=dt.datetime.now(KST),'future asOf')
    keys=set()
    for region,field in [('foreign','foreignNews'),('domestic','domesticNews')]:
        news=s[field]
        require(isinstance(news,list) and len(news)<=10, 'news limit')
        for rank,n in enumerate(news,1):
            require(all(isinstance(n.get(k),str) and n[k].strip() for k in ('id','title','summary','sourceName','category')), 'news strings')
            require(n['region']==region and n['impactRank']==rank,'region/rank')
            require(n['id'] not in keys,'duplicate id')
            keys.add(n['id'])
            require(timestamp(n['publishedAt'])<=cutoff,'news after cutoff')
            require(https(n['sourceUrl']),'HTTPS source required')
            require(isinstance(n['relatedStocks'],list) and all(isinstance(x,str) for x in n['relatedStocks']),'relatedStocks')
    themes=s['usThemes']
    require(isinstance(themes,list) and len(themes)<=3,'theme limit')
    require(s['slot']=='06:40' or not themes,'themes outside 06:40')
    if not strict:
        return
    require(s.get('researchStatus') in ('complete','partial','failed'),'researchStatus required')
    audit=s['researchAudit']
    domains=audit['domains']
    for key in ('foreignNews','domesticNews','usThemes'):
        d=domains[key]
        require(d['status'] in ('complete','partial','failed','not_applicable'),'domain status')
        require(d['status']!='not_applicable' or (key=='usThemes' and s['slot']!='06:40'),'invalid not_applicable')
        start,end=timestamp(d['windowStartExclusive']),timestamp(d['windowEndInclusive'])
        require(start<=end<=cutoff,'domain window')
        require(isinstance(d['pendingWindows'],list),'pending windows required')
        if d.get('completedThrough'):
            require(timestamp(d['completedThrough'])<=end,'completedThrough after end')
        if d['status']=='complete':
            require(d.get('completedThrough') and timestamp(d['completedThrough'])==end and not d['pendingWindows'],'incomplete domain marked complete')
    if s['researchStatus']=='complete':
        require(all(d['status'] in ('complete','not_applicable') for d in domains.values()),'partial domain marked complete')
    state=s.get('usThemeStatus')
    if s['slot']!='06:40':
        require(state=='not_applicable','theme status outside 06:40')
    else:
        require(state in ('verified_themes','verified_no_theme','insufficient_data'),'theme state')
        if state=='insufficient_data':
            require(not themes,'unverified themes')
        else:
            require(domains['usThemes']['status']=='complete','theme domain incomplete')
            require(bool(themes)==(state=='verified_themes'),'theme state and results mismatch')
            evidence=audit['usThemeEvidence']
            rows=evidence['universe']
            require(len(rows)==50 and len({r['ticker'] for r in rows})==50,'complete 50 required')
            require(sorted(r['dollarVolumeRank'] for r in rows)==list(range(1,51)),'rank completeness')
            for r in rows:
                require(finite(r['dollarVolume']) and r['dollarVolume']>0 and finite(r['regularChangePct']),'numeric universe values')
                require(https(r['sourceUrl']) and r['securityType'] in ('common','adr'),'universe evidence/type')
            universe={r['ticker']:r for r in rows}
            for t in themes:
                members=t['memberTickers']
                require(len(set(members))==len(members)>=2 and all(m in universe for m in members),'theme membership')
                denom=sum(universe[m]['dollarVolume'] for m in members)
                change=sum(universe[m]['dollarVolume']*universe[m]['regularChangePct'] for m in members)/denom
                require(change>0 and math.isclose(t['weightedChangePct'],change,abs_tol=0.0001),'theme weighted change')
                require(math.isclose(t['totalDollarVolume'],denom,rel_tol=1e-8),'theme turnover')
                require(len(t['stocks'])<=5 and all(r['ticker'] in members for r in t['stocks']),'display stocks')

def validate(body, today=None):
    today=today or dt.datetime.now(KST).date()
    require(body['schemaVersion']==1,'schemaVersion')
    timestamp(body['updatedAt'])
    seen=set()
    for d in body['days']:
        date=dt.date.fromisoformat(d['date'])
        require(today-dt.timedelta(days=3)<=date<=today,'outside FIFO range')
        require(date not in seen,'duplicate date')
        seen.add(date)
        require(type(d['isKrxTradingDay']) is bool,'trading flag')
        slots=set()
        for s in d['sessions']:
            require(s['slot'] not in slots,'duplicate slot')
            slots.add(s['slot'])
            validate_session(s,d['date'],d['isKrxTradingDay'])
    return body

def merge(current,draft,today=None):
    today=today or dt.datetime.now(KST).date()
    validate_session(draft['session'],draft['date'],draft['isKrxTradingDay'],strict=True)
    result=copy.deepcopy(current)
    # Before FIFO, preserve unresolved domain windows without retaining old content.
    state=result.setdefault('researchState',{})
    for historical in result['days']:
        for record in historical['sessions']:
            for key,domain in record.get('researchAudit',{}).get('domains',{}).items():
                if domain.get('pendingWindows'):
                    kept=state.setdefault(key,{'pendingWindows':[]})
                    for pending in domain['pendingWindows']:
                        if pending not in kept.setdefault('pendingWindows',[]):
                            kept['pendingWindows'].append(copy.deepcopy(pending))
    # Prune content only; outstanding windows remain in researchState.
    result['days']=[d for d in result['days'] if today-dt.timedelta(days=3)<=dt.date.fromisoformat(d['date'])<=today]
    validate(result,today)
    day=next((d for d in result['days'] if d['date']==draft['date']),None)
    if day is None:
        day={'date':draft['date'],'isKrxTradingDay':draft['isKrxTradingDay'],'sessions':[]}
        result['days'].append(day)
    require(day['isKrxTradingDay']==draft['isKrxTradingDay'],'trading evidence conflict')
    session=draft['session']
    old=next((s for s in day['sessions'] if s['slot']==session['slot']),None)
    require(old is None or timestamp(old['asOf'])<=timestamp(session['asOf']),'stale replacement')
    if 'researchState' in draft:
        previous=result.get('researchState',{})
        for key,value in previous.items():
            require(key in draft['researchState'],'researchState domain lost')
            proposed=draft['researchState'][key]
            if value.get('completedThrough') and proposed.get('completedThrough'):
                require(timestamp(proposed['completedThrough'])>=timestamp(value['completedThrough']),'watermark regression')
            for pending in value.get('pendingWindows',[]):
                completed=proposed.get('completedThrough')
                require(pending in proposed.get('pendingWindows',[]) or (completed and timestamp(completed)>=timestamp(pending['endInclusive'])),'unresolved window lost')
        result['researchState']=copy.deepcopy(draft['researchState'])
    day['sessions']=[s for s in day['sessions'] if s['slot']!=session['slot']]+[copy.deepcopy(session)]
    day['sessions'].sort(key=lambda s:s['slot'])
    result['days'].sort(key=lambda d:d['date'],reverse=True)
    result['updatedAt']=dt.datetime.now(KST).isoformat()
    return validate(result,today)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['validate','merge'])
    p.add_argument('files',nargs='+')
    p.add_argument('--today',type=dt.date.fromisoformat)
    a=p.parse_args()
    body=json.load(open(a.files[0]))
    if a.mode=='validate':
        validate(body,a.today)
        print('JSON structural validation passed; source research is not certified.')
    else:
        require(len(a.files)==3,'merge CURRENT DRAFT OUTPUT')
        result=merge(body,json.load(open(a.files[1])),a.today)
        with open(a.files[2],'w') as f: json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
