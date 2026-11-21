"""Source adapter for schema3. Raw responses retained even on a validation hold.

Naver ST alone does not certify individual-company instrument classification.
A dated, reviewed complete security master and market-scope proof are required.
"""
import datetime as dt
import json
import pathlib
from featured_v3 import KST, SLOTS, stamp, require, trading, rank_universe


def collect_integrated(release,evidence,fetch,now=None,trace=None,probe=False,eligibility_fetch=None):
    from featured_stocks import list_url, get_nxt_eligibility
    target=stamp(release);started=now or dt.datetime.now(KST);date=target.date().isoformat();slot=target.strftime('%H:%M')
    require(slot in SLOTS,'invalid original slot')
    require(started.date()==target.date(),'cannot recollect a historical trading date')
    trading(evidence.get('tradingDayEvidence',{}),date)
    raw={};errors={};records=[]
    for venue in ('KRX','NXT'):
        url=list_url(venue)
        try:
            raw[venue]=fetch(url);require(isinstance(raw[venue],list) and raw[venue],'empty/changed market response')
            retrieved=(now or dt.datetime.now(KST)).isoformat()
            records.append({'market':venue,'sourceUrl':url,'retrievedAt':retrieved})
            raw.setdefault('_retrievedAt',{})[venue]=retrieved
        except Exception as e:errors[venue]=type(e).__name__+': '+str(e)
    try:raw['NXT_OFFICIAL']=(eligibility_fetch or get_nxt_eligibility)()
    except Exception as e:errors['NXT_OFFICIAL']=type(e).__name__+': '+str(e)
    dest=pathlib.Path('collection-artifacts/integrated-'+target.strftime('%Y-%m-%d-%H%M')+'.json');dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps({'releaseAt':release,'queriedAt':(now or dt.datetime.now(KST)).isoformat(),'raw':raw,'errors':errors},ensure_ascii=False,indent=2)+'\n')
    if trace:trace({'stage':'integrated_source_queries','checkedAt':(now or dt.datetime.now(KST)).isoformat(),'evidencePath':str(dest),'errors':errors,'markets':list(raw)})
    require(not errors,'source unavailable: '+json.dumps(errors,ensure_ascii=False))
    # The normalized source package must bind to these just-fetched responses.
    # Do not trust an old hand-entered quote package as current market evidence.
    package=evidence.get('integratedSourcePackage')
    if package is None:
        from featured_naver_v3 import normalize
        package=normalize(raw,release,fetch,now=now,trace=trace)
    else:
        require(isinstance(package,dict) and package.get('rawResponses')==raw,'normalized package does not match actual source responses')
    ended=now or dt.datetime.now(KST)
    stocks,proof=rank_universe(package['securityMaster'],package['krxQuotes'],package['nxtQuotes'],package['coverage'],date,ended,slot)
    if trace:trace({'stage':'integrated_top100_verified','checkedAt':ended.isoformat(),'stockCount':100,'cutoffAmount':proof['cutoffAmount']})
    return {'schemaVersion':3,'date':date,'slot':slot,'releaseAt':target.isoformat(),'asOf':ended.isoformat(),'collectionStartedAt':started.isoformat(),
        'turnoverBasis':'KRX_NXT','universeSize':100,'amountUnit':'KRW','rateBasis':'KRX_PREVIOUS_CLOSE',
        'priceSession':'AFTER' if slot=='20:10' else 'REGULAR','stocks':stocks,'rankingProof':proof,
        'tradingDayEvidence':evidence['tradingDayEvidence'],'tradingDayVerified':True,'calendarSourceUrl':evidence['tradingDayEvidence']['sourceUrl'],
        'sourceRecords':records,'serverRetentionCalendarDays':2,'appVisibleCalendarDays':2,'probeOnly':probe}
