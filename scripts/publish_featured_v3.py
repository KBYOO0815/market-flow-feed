"""Same-commit read/merge/atomic public publication and verified optional private mirror."""
import base64
import copy
import datetime as dt
import json
import hashlib
import os
import re
import urllib.error
import urllib.request
from featured_v3 import KST, stamp, validate, require


def publication_view(payload):
    """Keep full-market proof once, not repeated in every mobile day/session."""
    public=copy.deepcopy(payload);proof=public['rankingProof']
    if 'allMarketRows' not in proof:return public,None,None
    full=copy.deepcopy(proof)
    content=json.dumps(full,ensure_ascii=False,indent=2)+'\n'
    encoded=content.encode();sha=hashlib.sha1(('blob '+str(len(encoded))+'\0').encode()+encoded).hexdigest()
    path='collections/featured-proofs/'+public['date']+'-'+public['slot'].replace(':','')+'-'+sha+'.json'
    proof.pop('allMarketRows');proof.update(evidencePath=path,evidenceBlobSha=sha)
    return public,path,full


def merge(payload,days,today):
    cutoff=(today-dt.timedelta(days=1)).isoformat();upper=today.isoformat()
    retained={d:copy.deepcopy(v) for d,v in days.items() if cutoff<=d<=upper}
    day=retained.setdefault(payload['date'],{'date':payload['date'],'editions':{}})
    old=day['editions'].get(payload['slot'])
    if old:require(stamp(payload['asOf'])>=stamp(old['asOf']),'refusing older replacement')
    day['editions'][payload['slot']]=copy.deepcopy(payload)
    for d in retained:
        require(len(retained[d]['editions'])<=5,'too many daily editions')
        retained[d]['editions']=dict(sorted(retained[d]['editions'].items(),reverse=True))
    latest=max((p for v in retained.values() for p in v['editions'].values()),key=lambda p:(stamp(p['releaseAt']),stamp(p['asOf'])))
    root=copy.deepcopy(latest);root['days']=[retained[d] for d in sorted(retained,reverse=True)]
    return root,retained


def publish(payload,api,read,clock=lambda:dt.datetime.now(KST)):
    validate(payload);require(payload['schemaVersion']==3,'v3 publisher only')
    for attempt in range(3):
        now=clock();require(now.date().isoformat()==payload['date'],'no historical publication')
        require(stamp(payload['reviewedAt'])<=now,'future review')
        final=copy.deepcopy(payload);final['publishedAt']=now.isoformat();final['status']['publication']='success';validate(final)
        final,proof_path,proof_body=publication_view(final)
        head=api('GET','git/ref/heads/main')['object']['sha'];commit=api('GET','git/commits/'+head)
        tree=api('GET','git/trees/'+commit['tree']['sha']+'?recursive=1')
        paths=[x['path'] for x in tree['tree'] if re.fullmatch(r'featured-stocks/\d{4}-\d{2}-\d{2}\.json',x['path'])]
        days={}
        for path in paths:days[path[-15:-5]]=read(path,head)[0]
        root,retained=merge(final,days,now.date())
        index={'schemaVersion':3,'appVisibleCalendarDays':2,'releaseAt':root['releaseAt'],'asOf':root['asOf'],
            'dates':[{'date':d,'path':'featured-stocks/'+d+'.json'} for d in sorted(retained,reverse=True)]}
        contents={'featured-stocks.json':root,'featured-stocks/index.json':index,**{'featured-stocks/'+d+'.json':day for d,day in retained.items()}}
        if proof_path:contents[proof_path]=proof_body
        entries=[{'path':p,'mode':'100644','type':'blob','content':json.dumps(v,ensure_ascii=False,indent=2)+'\n'} for p,v in contents.items()]
        for path in paths:
            if path[-15:-5] not in retained:entries.append({'path':path,'mode':'100644','type':'blob','sha':None})
        # Retain an immutable byte-identical migration backup before first v3 root.
        current,sha=read('featured-stocks.json',head,missing=True)
        if current and current.get('schemaVersion')!=3:
            entries.append({'path':'backups/featured-stocks/pre-v3-'+sha+'.json','mode':'100644','type':'blob','sha':sha})
        newtree=api('POST','git/trees',{'base_tree':commit['tree']['sha'],'tree':entries})
        new=api('POST','git/commits',{'message':'Publish verified integrated Top100 '+final['releaseAt'],'tree':newtree['sha'],'parents':[head]})
        try:api('PATCH','git/refs/heads/main',{'sha':new['sha'],'force':False})
        except urllib.error.HTTPError as e:
            if e.code not in (409,422) or attempt==2:raise
            continue
        for path,expected in contents.items():
            require(read(path,new['sha'])[0]==expected,'remote readback mismatch: '+path)
        actualtree=api('GET','git/trees/'+newtree['sha']+'?recursive=1')
        require(not any(x['path'] in paths and x['path'][-15:-5] not in retained for x in actualtree['tree']),'FIFO deletion readback failed')
        return new['sha']
    raise RuntimeError('publication conflict retries exhausted')


def mirror(root,token):
    require(bool(token),'APP_MIRROR_TOKEN is not configured; public success is not mirror success')
    url='https://api.github.com/repos/KBYOO0815/market-flow-app/contents/data/featured-stocks.json'
    def request(method,body=None,resource_url=None):
        r=urllib.request.Request(resource_url or url,data=json.dumps(body).encode() if body else None,method=method,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json'})
        with urllib.request.urlopen(r,timeout=30) as response:return json.load(response)
    def decode(obj):
        if obj.get('encoding')!='base64' or not obj.get('content'):
            obj=request('GET',resource_url='https://api.github.com/repos/KBYOO0815/market-flow-app/git/blobs/'+obj['sha'])
        return json.loads(base64.b64decode(obj['content']))
    for attempt in range(3):
        obj=request('GET');current=decode(obj)
        require(stamp(current['releaseAt'])<=stamp(root['releaseAt']),'mirror rollback forbidden')
        try:request('PUT',{'message':'Mirror verified featured stocks '+root['releaseAt'],'sha':obj['sha'],'content':base64.b64encode((json.dumps(root,ensure_ascii=False,indent=2)+'\n').encode()).decode()})
        except urllib.error.HTTPError as e:
            if e.code not in (409,422) or attempt==2:raise
            continue
        require(decode(request('GET'))==root,'private mirror readback mismatch');return True
    raise RuntimeError('mirror conflict retries exhausted')
