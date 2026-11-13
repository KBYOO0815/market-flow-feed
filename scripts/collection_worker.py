"""Server collection and health records, never publication."""
import datetime as dt
import json
import os
import pathlib
import re
import copy
from featured_stocks import KST, collect, get, get_nxt_eligibility, list_url, stamp
from publish_feed import api
from source_http import CollectionFetch
from featured_stocks import BASE


def write_artifact(ident, status):
    pathlib.Path('collection-artifacts').mkdir(exist_ok=True)
    pathlib.Path('collection-artifacts/'+ident+'.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')


def save(entries):
    for attempt in range(3):
        head=api('GET','git/ref/heads/main')['object']['sha']
        commit=api('GET','git/commits/'+head)
        tree=api('POST','git/trees',{'base_tree':commit['tree']['sha'],'tree':[
            {'path':p,'mode':'100644','type':'blob','content':json.dumps(v,ensure_ascii=False,indent=2)+'\n'} for p,v in entries.items()]})
        new=api('POST','git/commits',{'message':'Record collection status (not publication)','tree':tree['sha'],'parents':[head]})
        try:
            api('PATCH','git/refs/heads/main',{'sha':new['sha'],'force':False});return
        except Exception as e:
            if getattr(e,'code',None) not in (409,422) or attempt==2:raise


def run(request):
    ident=request['requestId']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',ident):raise ValueError('invalid requestId')
    path='operations/collections/'+ident+'.json'
    started=dt.datetime.now(KST)
    status={'requestId':ident,'releaseAt':request.get('releaseAt'),'published':False,'state':'collecting',
            'startedAt':started.isoformat(),'deadlineAt':(started+dt.timedelta(minutes=5)).isoformat()}
    status['progress'] = []
    save({path:copy.deepcopy(status)})
    try:
        entries={}
        if request.get('mode')=='probe':
            ranks={m:get(list_url(m)) for m in ('KRX','NXT')};official=get_nxt_eligibility()
            if not all(isinstance(v,list) and v for v in ranks.values()):raise ValueError('ranking shape changed')
            if not isinstance(official.get('brdinfoTimeList'),list):raise ValueError('official list shape changed')
            # Network load probe only, not an integrated ranking or a publishable edition.
            krx_top=sorted((r for r in ranks['KRX'] if r.get('type')=='ST'),key=lambda r:-int(r['tradeAmount']))[:50]
            eligible={r['isuSrdCd'].removeprefix('A') for r in official['brdinfoTimeList']}
            urls=[BASE+'detail/'+r['itemcode']+'/detail?codeType='+m for r in krx_top
                  for m in (('KRX','NXT') if r['itemcode'] in eligible else ('KRX',))]
            cache=CollectionFetch(get);cache.prime(urls)
            for url in urls:
                quote=cache(url)
                if not quote.get('tradeTime'):raise ValueError('detail observation missing')
            status['probeDetailRequests']=len(set(urls))
            status['probeDetailSucceeded']=len(cache.values)
            status.update(state='probe_passed',scope='network_connectivity_and_load_only',freshnessValidated=False,rankingRows={m:len(v) for m,v in ranks.items()},officialRows=len(official['brdinfoTimeList']),officialObservedAt=official.get('setTime'))
        else:
            def progress(event):
                status['progress'].append(event)
                status['lastStage'] = event['stage']
                # Keep local evidence even if a later source or repository write fails.
                write_artifact(ident, status)
            is_probe = request.get('mode') == 'collect_probe'
            if request.get('mode') not in ('collect', 'collect_probe', None):
                raise ValueError('unknown collection mode')
            snapshot=collect(request['releaseAt'],request['evidence'],trace=progress,probe=is_probe,full_nxt=True)
            dest='collections/featured-stocks/'+ident+'.json';entries[dest]=snapshot
            status.update(state='probe_collected' if is_probe else 'collected',snapshotPath=dest,stockCount=len(snapshot['stocks']),
                          publicationEligible=not is_probe, freshnessValidated=not is_probe)
        status['completedAt']=dt.datetime.now(KST).isoformat()
        status['elapsedSeconds']=(stamp(status['completedAt'])-started).total_seconds()
        entries[path]=copy.deepcopy(status);save(entries)
        write_artifact(ident, status)
    except Exception as e:
        status.update(state='collection_failed',errorType=type(e).__name__,error=str(e),completedAt=dt.datetime.now(KST).isoformat())
        write_artifact(ident, status)
        save({path:status});raise


if __name__=='__main__':
    if os.environ.get('GITHUB_REPOSITORY')!='KBYOO0815/market-flow-feed':raise SystemExit('public data repo only')
    run(json.loads(pathlib.Path('requests/featured-collection.json').read_text()))
