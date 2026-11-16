"""Local-only synthetic publication lab. No credentials or remote writes."""
import base64, copy, datetime as dt, json, os, pathlib, subprocess, tempfile, threading
import urllib.error, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import publish_featured_stocks as fp
import publish_feed as bp
import featured_watch as fw
import briefing_watch as bw
from featured_stocks import enrich, validate, KST
from test_featured_hundred import snapshot
from test_featured_strength import group
from test_editorial_rules import payload as briefing_payload
from prepare_feed import validate as validate_briefing

OUT=pathlib.Path('evidence'); OUT.mkdir(exist_ok=True)
class GitLab:
    def __init__(self):
        self.path=tempfile.mkdtemp(prefix='market-flow-e2e-')
        self.git('init','--initial-branch=main')
        self.git('config','user.name','E2E TEST ONLY')
        self.git('config','user.email','e2e@example.invalid')
        self.git('commit','--allow-empty','-m','Test-only empty feed')
        self.failures=set(); self.events=[]; self.lock=threading.RLock()
    def git(self,*args,input=None,env=None):
        output=subprocess.run(['git','-C',self.path,*args],input=input,env=env,
                              check=True,capture_output=True).stdout.decode()
        return output if args[0]=='show' else output.strip()
    def read(self,path,ref='main',missing=False):
        try:return json.loads(self.git('show',ref+':'+path)),self.git('rev-parse',ref+':'+path)
        except subprocess.CalledProcessError:
            if missing:return None,None
            raise urllib.error.HTTPError(path,404,'missing',{},None)
    def api(self,method,path,body=None):
        if path=='git/ref/heads/main':return {'object':{'sha':self.git('rev-parse','main')}}
        if path.startswith('git/commits/'):return {'tree':{'sha':self.git('rev-parse',path.split('/')[-1]+'^{tree}')}}
        if method=='GET' and path.startswith('git/trees/'):
            return {'tree':[{'path':p} for p in self.git('ls-tree','-r','--name-only',path.split('/')[-1].split('?')[0]).splitlines()]}
        if method=='POST' and path=='git/trees':
            index=os.path.join(self.path,'test-index'); env={**os.environ,'GIT_INDEX_FILE':index}
            self.git('read-tree',body['base_tree'],env=env)
            for e in body['tree']:
                if e.get('sha','present') is None:self.git('update-index','--force-remove',e['path'],env=env)
                else:
                    blob=self.git('hash-object','-w','--stdin',input=e['content'].encode())
                    self.git('update-index','--add','--cacheinfo','100644',blob,e['path'],env=env)
            return {'sha':self.git('write-tree',env=env)}
        if method=='POST' and path=='git/commits':
            return {'sha':self.git('commit-tree',body['tree'],'-p',body['parents'][0],input=body['message'].encode())}
        if method=='PATCH' and path=='git/refs/heads/main':
            self.git('update-ref','refs/heads/main',body['sha']); return {}
        if method=='GET' and path.startswith('contents/'):
            name,ref=path[len('contents/'):].split('?ref=')
            return {'content':base64.b64encode(self.git('show',ref+':'+name).encode()).decode()}
        raise AssertionError((method,path))
    def seed(self):
        p=briefing_payload()
        p['items'][0]['title']='E2E_INITIAL_BRIEFING'
        validate_briefing(p)
        t=self.api('POST','git/trees',{'base_tree':self.git('rev-parse','main^{tree}'),'tree':[
            {'path':'morning-briefing.json','content':json.dumps(p)},
            {'path':'briefings/2026-11-13.json','content':json.dumps({'date':'2026-11-13','editions':{'11:50':p}})}]})
        c=self.api('POST','git/commits',{'tree':t['sha'],'parents':[self.git('rev-parse','main')],'message':'Synthetic initial briefing'})
        self.api('PATCH','git/refs/heads/main',c)
    def stage(self,path,payload):
        tree=self.api('POST','git/trees',{'base_tree':self.git('rev-parse','main^{tree}'),
            'tree':[{'path':path,'content':json.dumps(payload,ensure_ascii=False)}]})
        commit=self.api('POST','git/commits',{'tree':tree['sha'],'parents':[self.git('rev-parse','main')],
            'message':'Stage synthetic original-edition draft'})
        self.api('PATCH','git/refs/heads/main',commit)
    def featured(self,empty=False):
        from test_featured_v3 import fixture
        from featured_v3 import rank_universe, enrich as enrich3
        from publish_featured_v3 import publish as publish3
        p=fixture()
        if empty:
            p['asOf']=(dt.datetime.fromisoformat(p['asOf'])+dt.timedelta(seconds=1)).isoformat();p['reviewedAt']=p['asOf']
            rows=p['rankingProof']['allMarketRows']
            for row in rows:row['quotes']['KRX']['price']=103
            p['stocks'],p['rankingProof']=rank_universe(rows,[r['quotes']['KRX'] for r in rows],[r['quotes']['NXT'] for r in rows],p['rankingProof'],p['date'],dt.datetime.fromisoformat(p['asOf']),p['slot'])
            p=enrich3(p,{'reviewedAt':p['reviewedAt'],'themes':[]})
        else:
            codes=p['selectedStockCodes'];groups=[]
            for j in range(5):
                members=codes[j*2:j*2+2]
                groups.append({'id':'e2e-'+str(j),'name':'E2E_THEME_'+str(j+1),'stockCodes':members,'groupingBasis':'industry','reason':None,'membershipEvidence':[{'code':c,'sourceUrl':'https://example.org','fact':'TEST ONLY'} for c in members]})
            p=enrich3(p,{'reviewedAt':p['reviewedAt'],'themes':groups})
        prefix='featured-stocks'
        self.stage('drafts/featured-stocks.json',p)
        private=GitLab();private.stage('data/drafts/featured-stocks.json',p)
        assert private.read('data/drafts/featured-stocks.json')[0]==self.read('drafts/featured-stocks.json')[0]
        records=[];clock=lambda:dt.datetime(2026,11,16,13,45,tzinfo=KST)
        with patch('publish_featured_v3.mirror',return_value=True):
            state=fw.watch(dt.datetime.fromisoformat(p['releaseAt']),records.append,
                read=self.read,write=lambda d:publish3(d,self.api,self.read,clock=clock),clock=clock)
        commit=state['commit'];root,_=self.read(prefix+'.json',commit);day,_=self.read(prefix+'/'+p['date']+'.json',commit)
        assert {k:v for k,v in root.items() if k!='days'}==day['editions'][p['slot']]
        assert root['asOf']==p['asOf'] and root['stocks']==p['stocks']
        private.stage('data/featured-stocks.json',root)
        assert private.read('data/featured-stocks.json')[0]==root
        event={'scenario':'empty_themes' if empty else 'five_themes','commit':commit,'stocks':len(p['stocks']),'themes':len(p['themes']),'rootArchiveMatch':True,'draftsMatch':True,'privateMirrorMatch':True,'watcherState':state['state'],'testClock':clock().isoformat()}
        self.events.append(event);self.save();return event
    def briefing(self):
        p=briefing_payload();p['releaseAt']='2026-11-13T20:20:00+09:00';p['asOf']='2026-11-13T20:20:00+09:00'
        p['selectionAudit']['endAt']=p['asOf']
        for row in p['researchAudit']['coverage'].values():row['checkedAt']=p['asOf']
        x=p['items'][0]; x['id']='e2e-new';x['title']='E2E_PUBLISHED_BRIEFING';x['reviewedAt']=p['asOf']
        x['publishedAt']='2026-11-13T20:15:00+09:00';x['validUntil']='2026-11-16T06:40:00+09:00'
        x['selection']['eventKey']='e2e-new-event';x['selection']['eventAt']=x['publishedAt']
        x['selection']['facts'][0].update(key='e2e-new-fact',occurredAt=x['publishedAt'])
        validate_briefing(p)
        self.stage('drafts/morning-briefing.json',p)
        private=GitLab();private.stage('data/drafts/morning-briefing.json',p)
        assert private.read('data/drafts/morning-briefing.json')[0]==self.read('drafts/morning-briefing.json')[0]
        with patch.object(bp,'api',side_effect=self.api),patch.object(bp,'read_remote',side_effect=self.read):
            state=bw.watch(dt.datetime.fromisoformat(p['releaseAt']),lambda value:None,
                read=self.read,write=bp.publish,clock=lambda:dt.datetime(2026,11,13,20,25,tzinfo=KST))
            commit=state['commit']
        assert self.read('morning-briefing.json',commit)[0]==self.read('briefings/2026-11-13.json',commit)[0]['editions']['20:20']
        private.stage('data/morning-briefing.json',p)
        assert private.read('data/morning-briefing.json')[0]==p
        event={'scenario':'briefing','commit':commit,'rootArchiveMatch':True,'draftsMatch':True,'privateMirrorMatch':True,'watcherState':state['state'],'testClock':'2026-11-13T20:25:00+09:00'}
        self.events.append(event);self.save();return event
    def save(self):(OUT/'local-publications.json').write_text(json.dumps(self.events,ensure_ascii=False,indent=2))
lab=GitLab();lab.seed()
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        action=self.path.rsplit('/',1)[-1]
        with lab.lock:
            if action=='five':result=lab.featured()
            elif action=='empty':result=lab.featured(True)
            elif action=='briefing':result=lab.briefing()
            elif action=='legacy-error':lab.failures={'legacy'};result={'injected':'legacy HTTP 503'}
            elif action=='malformed':lab.failures={'malformed'};result={'injected':'v2 invalid payload'}
            elif action=='recover':lab.failures=set();result={'recovered':True}
            else:raise ValueError(action)
        body=json.dumps(result).encode();self.send_response(200);self.end_headers();self.wfile.write(body)
    def do_GET(self):
        name=urllib.parse.urlparse(self.path).path.lstrip('/')
        with lab.lock:
            if ('legacy' in lab.failures and name.startswith('featured-stocks/')):self.send_response(503);self.end_headers();return
            if 'malformed' in lab.failures and name=='featured-stocks-v2/2026-11-13.json':
                body=json.dumps({'date':'2026-11-13','editions':{'20:10':{'schemaVersion':2,'releaseAt':'2026-11-13T20:10:00+09:00'}}}).encode()
            else:
                try:body=lab.git('show','main:'+name).encode()
                except subprocess.CalledProcessError:self.send_response(404);self.end_headers();return
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',8765),Handler).serve_forever()
