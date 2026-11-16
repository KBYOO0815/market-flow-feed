"""Fast publication regression checks; disposable Git repos, no network writes."""
import datetime as dt,json,pathlib,sys
from unittest.mock import Mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent/'e2e'))
import publication_server as s
a=s.lab.featured();b=s.lab.featured(True);c=s.lab.briefing()
assert a['stocks']==100 and a['themes']==5
assert b['stocks']==100 and b['themes']==0
assert all(x['rootArchiveMatch'] and x['draftsMatch'] and x['privateMirrorMatch'] and x['watcherState']=='published' for x in (a,b,c))
draft=s.lab.read('drafts/featured-stocks.json')[0]
fresh=s.GitLab();fresh.stage('drafts/featured-stocks.json',draft)
records=[];write=Mock();release=dt.datetime.fromisoformat(draft['releaseAt'])
try:s.fw.watch(release,records.append,read=fresh.read,write=write,clock=lambda:release+dt.timedelta(minutes=31))
except RuntimeError:pass
assert records[-1]['state']=='publication_missed';write.assert_not_called()
state=s.fw.watch(release,lambda value:None,read=s.lab.read,write=write,clock=lambda:release+dt.timedelta(minutes=60))
assert state['alreadyPublished'];write.assert_not_called()
print(json.dumps({'syntheticOnly':True,'productionWrites':False,'publications':s.lab.events,'expiredEdition':'publication_missed','duplicateEdition':'alreadyPublished'},ensure_ascii=False))
