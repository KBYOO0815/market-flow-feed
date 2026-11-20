"""Normalize the bounded KRX/NXT Top100 union into reproducible evidence.

The venue rankings define candidates.  Every candidate is classified against
the dated KIS master and its actual KRX/NXT venue amounts are then queried in
bounded batches.  A missing venue quote is never converted to zero.
"""
import datetime as dt
import json
import pathlib
from featured_master import probe as master_probe
from featured_v3 import KST, require, stamp, num
from source_http import CollectionFetch


def normalize(raw,release,fetch,now=None,trace=None):
    from featured_stocks import BASE,NXT_ELIGIBILITY_URL,list_url,official_zero_nxt
    target=stamp(release);date=target.date().isoformat();clock=lambda:now or dt.datetime.now(KST)
    start=clock();master_status=master_probe();master={};universe=[]
    for market,basename in [('KOSPI','kospi'),('KOSDAQ','kosdaq')]:
        require('error' not in master_status[market],'security master unavailable: '+str(master_status[market]))
        body=json.loads(pathlib.Path('collection-artifacts/'+basename+'-master-probe.json').read_text())
        require(dt.date(*body['zipFileTimestamp'][:3])==target.date(),'security master not generated on this trading date')
        for row in body['rows']:
            require(row['code'] not in master,'master duplicate across exchanges')
            master[row['code']]={**row,'market':market,'sourceUrl':body['sourceUrl'],'masterRetrievedAt':body['retrievedAt']}
    ranked={};thresholds={}
    for venue in ('KRX','NXT'):
        rows=raw[venue]
        require(isinstance(rows,list) and len(rows)>=100,venue+' ranking has fewer than 100 rows')
        require(len(rows)==len({r.get('itemcode') for r in rows}),venue+' ranking duplicate identity')
        for r in rows:
            require(r.get('itemcode') and str(r.get('tradeAmount','')).isdigit(),venue+' ranking identity/turnover invalid')
        ranked[venue]=sorted(rows,key=lambda r:(-int(r['tradeAmount']),r['itemcode']))[:100]
        require(len(ranked[venue])==100,venue+' Top100 incomplete')
        thresholds[venue]=int(ranked[venue][-1]['tradeAmount'])
    allkrx={r['itemcode']:r for r in raw['KRX']}
    official=raw['NXT_OFFICIAL'];official_zero_nxt([],{},official,clock())
    official_observed=dt.datetime.strptime(official['setTime'],'%Y-%m-%d %H:%M').replace(tzinfo=KST)
    official_codes={r['isuSrdCd'].removeprefix('A') for r in official['brdinfoTimeList']}
    require({r['itemcode'] for r in ranked['NXT']}<=official_codes,'NXT Top100 contradicts official NXT eligibility')
    candidates={}
    for venue in ('KRX','NXT'):
        for r in ranked[venue]:
            if r.get('type') not in ('ST','FS'):continue
            code=r['itemcode'];m=master.get(code)
            require(m is not None,venue+' Top100 stock absent from current master: '+code)
            require(r.get('type')==m['groupCode'],'security type contradicts broker master: '+code)
            if m['spacFlag']=='Y':continue
            require(m['spacFlag']=='N' and m['preferredCode'] in ('0','1','2','9'),'unrecognized security classification: '+code)
            candidates[code]={'code':code,'name':r.get('itemname') or m['name'],'market':m['market'],'securityType':'COMMON' if m['preferredCode']=='0' else 'PREFERRED',
                'classificationVerified':True,'classificationSourceUrl':m['sourceUrl'],
                'classificationEvidence':{'naverType':r['type'],'brokerGroup':m['groupCode'],'spacFlag':m['spacFlag'],'preferredCode':m['preferredCode'],'masterRetrievedAt':m['masterRetrievedAt']}}
    candidate_codes=sorted(candidates);require(len(candidate_codes)>=100,'eligible KRX/NXT Top100 union has fewer than 100 candidates; expand source rankings')
    source_union={r['itemcode'] for venue in ('KRX','NXT') for r in ranked[venue]}
    excluded_codes=sorted(source_union-set(candidate_codes))
    universe=[candidates[c] for c in candidate_codes]
    nxt_codes=sorted(official_codes & set(candidate_codes));cache=CollectionFetch(fetch)
    request_count=len(candidate_codes)+len(nxt_codes)
    if trace:trace({'stage':'integrated_union_scan_started','checkedAt':clock().isoformat(),'candidateCount':len(candidate_codes),'nxtCandidateCount':len(nxt_codes),'requestCount':request_count,'batchSize':40})
    for start_index in range(0,len(candidate_codes),40):
        batch_codes=candidate_codes[start_index:start_index+40]
        urls=[BASE+'detail/'+c+'/detail?codeType='+venue for c in batch_codes for venue in (('KRX','NXT') if c in official_codes else ('KRX',))]
        try:
            # Production get() already applies the three-attempt transport cap.
            cache.prime(urls)
        except Exception as error:
            pathlib.Path('collection-artifacts/integrated-partial-quotes.json').write_text(json.dumps({'completed':len(cache.values),'sourceUrl':getattr(error,'url',None),'error':str(error),'quotes':cache.values},ensure_ascii=False,indent=2)+'\n')
            if trace:trace({'stage':'integrated_union_source_failed','checkedAt':clock().isoformat(),'completed':len(cache.values),'sourceUrl':getattr(error,'url',None),'error':str(error),'transportAttemptLimit':3})
            raise
        if trace:trace({'stage':'integrated_union_scan_progress','checkedAt':clock().isoformat(),'completedCandidates':min(start_index+40,len(candidate_codes)),'totalCandidates':len(candidate_codes)})
        require(clock()-start<=dt.timedelta(minutes=5),'complete market scan exceeded five minutes; no publication')
    venues={};issues=[]
    for venue,codes in [('KRX',candidate_codes),('NXT',nxt_codes)]:
        result=[]
        for code in codes:
            url=BASE+'detail/'+code+'/detail?codeType='+venue
            try:
                q=cache(url);retrieved=(now or cache.times[url].astimezone(KST));observed=dt.datetime.strptime(q['tradeTime'],'%Y%m%d%H%M%S').replace(tzinfo=KST)
                require(q.get('itemcode')==code and observed.date()==target.date(),'quote identity/trading date mismatch')
                require(observed<=retrieved,'future market quote')
                amount=int(q['tradeAmount']);require(str(q['tradeAmount']).isdigit(),'invalid turnover')
                source_session=q.get('tradingSessionType')
                final_confirmed=False
                if venue=='KRX':
                    regular_close=(observed.hour==15 and observed.minute==30 and source_session in ('REGULAR_MARKET','REGULAR_CLOSE'))
                    allow_after=target.strftime('%H:%M') in ('15:40','20:10') and source_session=='AFTER_MARKET'
                    require(source_session in ('REGULAR_MARKET','REGULAR_CLOSE') or allow_after,'aftermarket price is not valid for this slot')
                    session='REGULAR_CLOSE' if regular_close else 'KRX_AFTER_MARKET' if source_session=='AFTER_MARKET' else 'REGULAR_MARKET'
                    final_confirmed=session=='KRX_AFTER_MARKET' and target.strftime('%H:%M')=='20:10' and retrieved>=target
                else:
                    regular_close=False
                    if target.strftime('%H:%M')=='20:10':
                        require(retrieved>=target,'20:10 NXT quote retrieved before release slot')
                        require(official_observed.date()==target.date() and official_observed.time()>=dt.time(20,0),'NXT official final snapshot is before after-market close')
                        session='NXT_FINAL';final_confirmed=True
                    else:
                        session='NXT_CUMULATIVE'
                quote={'code':code,'market':venue,'tradeDate':date,'turnoverScope':venue+'_ONLY','sourceUrl':url,'retrievedAt':retrieved.isoformat(),'observedAt':observed.isoformat(),
                    'turnover':amount,'session':session,'closeConfirmed':regular_close,'finalConfirmed':final_confirmed}
                price=num(q['nowPrice']);require(price>0,'invalid observed price')
                quote.update(price=float(price),priceSourceUrl=url)
                if venue=='KRX':
                    base=num(master[code]['referencePrice'])
                    new_listing=(allkrx.get(code) or {}).get('listedDate',master[code].get('listingDate'))==target.strftime('%Y%m%d')
                    confirmed=master[code].get('exRightsCode')=='00'
                    require(base>0,'invalid observed reference')
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
    require(not issues,'candidate market normalization incomplete; '+str(len(issues))+' quote issues; evidence='+str(evidence)+'; first='+str(issues[:2]))
    boundary=thresholds['KRX']+thresholds['NXT']
    return {'securityMaster':universe,'krxQuotes':venues['KRX'],'nxtQuotes':venues['NXT'],'coverage':{'date':date,'method':'top100_union_boundary','securityMasterComplete':True,
        'sourceTop100Complete':True,'candidateMasterComplete':True,'candidateMarketAmountsComplete':True,'candidateCodes':candidate_codes,'candidateCount':len(candidate_codes),
        'krxTop100Codes':[r['itemcode'] for r in ranked['KRX']],'nxtTop100Codes':[r['itemcode'] for r in ranked['NXT']],
        'excludedTop100Codes':excluded_codes,
        'krxRank100Amount':thresholds['KRX'],'nxtRank100Amount':thresholds['NXT'],'boundaryUpperBound':boundary,
        'rankingSourceUrls':{'KRX':list_url('KRX'),'NXT':list_url('NXT')},'rankingRetrievedAt':raw.get('_retrievedAt',start.isoformat()),
        'nxtEligibleCodes':nxt_codes,'sourceUrl':NXT_ELIGIBILITY_URL,'officialEligibleCount':official['totalCnt'],'officialObservedAt':official['setTime'],'masterStatus':master_status}}
