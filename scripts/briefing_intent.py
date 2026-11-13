"""Push-trigger an edition independently of delayed cron; diagnostics cannot publish."""
import datetime as dt
import json
import os
import pathlib
import re
from briefing_schedule import resolve
from prepare_feed import KST
from operation_store import save


def validate_intent(request, now):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',request.get('requestId','')):
        raise ValueError('invalid briefing intent requestId')
    mode=request.get('mode','prepare')
    if mode not in ('prepare','diagnostic'):raise ValueError('invalid briefing intent mode')
    release=resolve(now,release_at=request['releaseAt'])
    if mode=='prepare' and not release-dt.timedelta(minutes=20)<=now<=release+dt.timedelta(minutes=30):
        raise ValueError('original edition preparation/recovery window expired or not started')
    if mode=='diagnostic' and release.date()!=now.astimezone(KST).date():
        raise ValueError('diagnostic date must be today; never relabel historical research')
    return release,mode


def main():
    if os.environ.get('GITHUB_REPOSITORY')!='KBYOO0815/market-flow-feed':raise SystemExit('public feed repository only')
    request=json.loads(pathlib.Path('requests/briefing-run.json').read_text())
    now=dt.datetime.now(KST);release,mode=validate_intent(request,now)
    if len(__import__('sys').argv)>1 and __import__('sys').argv[1]=='diagnose':
        if mode!='diagnostic':raise ValueError('diagnostics require diagnostic mode')
        from briefing_preflight import collect
        record=collect(release)
        record.update(requestId=request['requestId'],state='diagnostic_only',publicationEligible=False,
                      published=False,diagnosticAt=dt.datetime.now(KST).isoformat())
        save('operations/briefing-diagnostics/'+request['requestId']+'.json',record)
    else:
        record={'requestId':request['requestId'],'releaseAt':release.isoformat(),'mode':mode,
                'state':'intent_accepted','checkedAt':now.isoformat(),
                'deadlineAt':(release+dt.timedelta(minutes=30)).isoformat(),
                'publicationEligible':mode=='prepare','published':False}
        save('operations/briefing-intents/'+request['requestId']+'.json',record)
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:
            f.write('release_at='+release.isoformat()+'\nmode='+mode+'\n')
    print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':main()
