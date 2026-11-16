"""Live public-source normalization. No manually relabelled observations.

KIS full master + Naver full KRX equities + every official NXT-eligible quote.
Aftermarket quotes are never interpreted as regular-session closing prices.
"""
import datetime as dt
import json
import pathlib
from featured_master import probe as master_probe
from featured_v3 import KST, require, stamp, num
from source_http import CollectionFetch


def normalize(raw,release,fetch,now=None,trace=None):
    from featured_stocks import BASE,NXT_ELIGIBILITY_URL,official_zero_nxt
    target=stamp(release);date=target.date().isoformat();clock=lambda:now or dt.datetime.now(KST)
    start=clock();master_status=master_probe();master={};universe=[]
    for market,basename in [('KOSPI','kospi'),('KOSDAQ','kosdaq')]:
        require('error' not in master_status[market],'security master unavailable: '+str(master_status[market]))
        body=json.loads(pathlib.Path('collection-artifacts/'+basename+'-master-probe.json').read_text())
        require(dt.date(*body['zipFileTimestamp'][:3])==target.date(),'security master not generated on this trading date')
        for row in body['rows']:
            require(row['code'] not in master,'master duplicate across exchanges')
            master[row['code']]={**row,'market':market,'sourceUrl':body['sourceUrl'],'masterRetrievedAt':body['retrievedAt']}
    rows=raw['KRX'];require(1000<len(rows)<5000,'KRX full universe truncated/changed')
    require(len(rows)==len({r['itemcode'] for r in rows}),'KRX ranking duplicate identity')
    allkrx={r['itemcode']:r for r in rows};eligible=[]
    for r in rows:
        if str(r.get('sosok')) not in ('0','1'):continue
        code=r['itemcode'];m=master.get(code)
        require(m is not None,'KRX listed security absent from current master: '+code)
        require(r.get('type')==m['groupCode'],'security type contradicts broker master: '+code)
        if r.get('type') not in ('ST','FS') or m['spacFlag']=='Y':continue
        require(m['spacFlag']=='N' and m['preferredCode'] in ('0','1','2','9'),'unrecognized security classification: '+code)
        eligible.append(code)
        universe.append({'code':code,'name':r['itemname'],'market':m['market'],'securityType':'COMMON' if m['preferredCode']=='0' else 'PREFERRED',
            'classificationVerified':True,'classificationSourceUrl':m['sourceUrl'],
            'classificationEvidence':{'naverType':r['type'],'brokerGroup':m['groupCode'],'spacFlag':m['spacFlag'],'preferredCode':m['preferredCode'],'masterRetrievedAt':m['masterRetrievedAt']}})
    # Expand outside the ranking when the complete master lists extra names.
    # Their actual venue quote is mandatory; a missing quote never becomes zero.
    expected={c for c,m in master.items() if m['groupCode'] in ('ST','FS') and m['spacFlag']=='N'}
    supplemental=sorted(expected-set(eligible))
    require(not set(eligible)-expected,'Naver eligible security absent from classified master')
    for code in supplemental:
        m=master[code]
        require(m['preferredCode'] in ('0','1','2','9'),'unknown supplemental share class')
        allkrx[code]={'itemcode':code,'itemname':m['name'],'type':m['groupCode'],'sosok':'0' if m['market']=='KOSPI' else '1','listedDate':m.get('listingDate')}
        eligible.append(code)
        universe.append({'code':code,'name':m['name'],'market':m['market'],'securityType':'COMMON' if m['preferredCode']=='0' else 'PREFERRED','classificationVerified':True,
            'classificationSourceUrl':m['sourceUrl'],'classificationEvidence':{'brokerGroup':m['groupCode'],'spacFlag':m['spacFlag'],'preferredCode':m['preferredCode'],'masterRetrievedAt':m['masterRetrievedAt'],'rankingSupplement':True}})
    if trace and supplemental:trace({'stage':'krx_ranking_candidates_expanded','checkedAt':clock().isoformat(),'supplementalCodes':supplemental})
    official=raw['NXT_OFFICIAL'];official_zero_nxt([],{},official,clock())
    official_codes={r['isuSrdCd'].removeprefix('A') for r in official['brdinfoTimeList']}
    require(official_codes<=set(allkrx),'official NXT listing absent from KRX master')
    nxt_codes=sorted(official_codes & set(eligible));cache=CollectionFetch(fetch)
    urls=[BASE+'detail/'+c+'/detail?codeType='+v for v,codes in [('KRX',sorted(eligible)),('NXT',nxt_codes)] for c in codes]
    if trace:trace({'stage':'full_integrated_scan_started','checkedAt':clock().isoformat(),'krxEligibleCount':len(eligible),'nxtEligibleCount':len(nxt_codes),'requestCount':len(urls)})
    for i in range(0,len(urls),60):
        try:cache.prime(urls[i:i+60])
        except Exception as error:
            pathlib.Path('collection-artifacts/integrated-partial-quotes.json').write_text(json.dumps({'completed':len(cache.values),'sourceUrl':getattr(error,'url',None),'error':str(error),'quotes':cache.values},ensure_ascii=False,indent=2)+'\n')
            if trace:trace({'stage':'full_integrated_scan_source_failed','checkedAt':clock().isoformat(),'completed':len(cache.values),'sourceUrl':getattr(error,'url',None),'error':str(error)})
            raise
        if trace:trace({'stage':'full_integrated_scan_progress','checkedAt':clock().isoformat(),'completed':min(i+60,len(urls)),'total':len(urls)})
        require(clock()-start<=dt.timedelta(minutes=5),'complete market scan exceeded five minutes; no publication')
    venues={};issues=[]
    for venue,codes in [('KRX',sorted(eligible)),('NXT',nxt_codes)]:
        result=[]
        for code in codes:
            url=BASE+'detail/'+code+'/detail?codeType='+venue
            try:
                q=cache(url);retrieved=(now or cache.times[url].astimezone(KST));observed=dt.datetime.strptime(q['tradeTime'],'%Y%m%d%H%M%S').replace(tzinfo=KST)
                require(q.get('itemcode')==code and observed.date()==target.date(),'quote identity/trading date mismatch')
                require(observed<=retrieved,'future market quote')
                amount=int(q['tradeAmount']);require(str(q['tradeAmount']).isdigit(),'invalid turnover')
                session=q.get('tradingSessionType')
                if venue=='KRX':
                    regular_close=(observed.hour==15 and observed.minute==30 and session in ('REGULAR_MARKET','REGULAR_CLOSE'))
                    require(session in ('REGULAR_MARKET','REGULAR_CLOSE') or target.strftime('%H:%M')=='15:40' and session=='AFTER_MARKET','aftermarket price is not KRX regular close')
                    session='REGULAR_CLOSE' if regular_close else 'KRX_AFTER_MARKET' if session=='AFTER_MARKET' else 'REGULAR_MARKET'
                else:
                    require(target.strftime('%H:%M')!='20:10','NXT official final total confirmation adapter required at20:10')
                    session='NXT_CUMULATIVE';regular_close=False
                quote={'code':code,'market':venue,'tradeDate':date,'turnoverScope':venue+'_ONLY','sourceUrl':url,'retrievedAt':retrieved.isoformat(),'observedAt':observed.isoformat(),
                    'turnover':amount,'session':session,'closeConfirmed':regular_close}
                if venue=='KRX':
                    price=num(q['nowPrice']);base=num(master[code]['referencePrice'])
                    new_listing=allkrx[code].get('listedDate')==target.strftime('%Y%m%d')
                    confirmed=master[code].get('exRightsCode')=='00'
                    require(price>0 and base>0,'invalid observed price/reference')
                    if session!='KRX_AFTER_MARKET':
                        change=num(q['prevChangePrice']);rate=num(q['prevChangeRate']);signed=-abs(change) if rate<0 else abs(change)
                        confirmed=confirmed and num(q.get('stdPrice'))==base and price-signed==base and abs((price/base-1)*100-rate)<=num('.011')
                    quote.update(price=float(price),previousRegularClose=None if new_listing else float(base),priceSourceUrl=url,
                        comparison={'eligible':confirmed and not new_listing,'basis':'UNAVAILABLE_NEW_LISTING' if new_listing else 'KRX_PREVIOUS_REGULAR_CLOSE' if confirmed else 'UNVERIFIED_ADJUSTED_REFERENCE',
                            'explanation':'신규상장: 전일 KRX 정규장 종가 없음; 별도 공식 기준가 검증 전 필터 제외' if new_listing else '당일 KIS 기준가 및 락구분00으로 전일 정규장 비교기준 검증; 장후 원문 자체 등락률 대신 KRX 실제 가격으로 재계산' if confirmed else '권리락/기준가 불일치: Top100 포함시 발행 차단',
                            'referenceSourceUrl':master[code]['sourceUrl']})
                result.append(quote)
            except Exception as e:issues.append({'market':venue,'code':code,'sourceUrl':url,'reason':type(e).__name__+': '+str(e)})
        venues[venue]=result
    pathlib.Path('collection-artifacts/integrated-raw-quotes.json').write_text(json.dumps(cache.values,ensure_ascii=False,indent=2)+'\n')
    evidence=pathlib.Path('collection-artifacts/integrated-normalization.json')
    evidence.write_text(json.dumps({'checkedAt':clock().isoformat(),'issues':issues,'masterStatus':master_status,'venueCounts':{v:len(q) for v,q in venues.items()}},ensure_ascii=False,indent=2)+'\n')
    require(not issues,'full market normalization incomplete; '+str(len(issues))+' quote issues; evidence='+str(evidence)+'; first='+str(issues[:2]))
    return {'securityMaster':universe,'krxQuotes':venues['KRX'],'nxtQuotes':venues['NXT'],'coverage':{'date':date,'securityMasterComplete':True,'krxComplete':True,'nxtComplete':True,
        'nxtEligibleCodes':nxt_codes,'sourceUrl':NXT_ELIGIBILITY_URL,'officialEligibleCount':official['totalCnt'],'officialObservedAt':official['setTime'],'masterStatus':master_status,'rankingSupplementCodes':supplemental}}
