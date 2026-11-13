"""Recover late featured-stock drafts for one original edition; never manufacture data."""
import datetime as dt
import os
import time
import urllib.error
from featured_stocks import KST, SLOTS, stamp, validate
from publish_featured_stocks import publish
from publish_feed import api, read_remote
from operation_store import save
from featured_scope import feed_prefix, release_prefix


def index_matches(index, payload):
    prefix=feed_prefix(payload)
    date=stamp(payload['releaseAt']).date()
    if (not isinstance(index,dict) or index.get('schemaVersion')!=payload['schemaVersion'] or index.get('appVisibleCalendarDays')!=2
        or index.get('releaseAt')!=payload['releaseAt'] or index.get('asOf')!=payload['asOf']
        or index.get('visibleUntil')!=dt.datetime.combine(date+dt.timedelta(days=2),dt.time(),KST).isoformat()):
        return False
    rows=index.get('dates',[])
    if not isinstance(rows,list) or not 1<=len(rows)<=2:
        return False
    expected={'date':date.isoformat(),'path':prefix+'/'+date.isoformat()+'.json'}
    try:
        return (expected in rows and len({r['date'] for r in rows})==len(rows) and
                all(date-dt.timedelta(days=1)<=dt.date.fromisoformat(r['date'])<=date
                    and r['path']==prefix+'/'+r['date']+'.json' for r in rows))
    except (KeyError,TypeError,ValueError):
        return False


def scheduled_release(created_at, cron):
    slots = {'40 0,2,4,6 * * 1-5': ('09:40','11:40','13:40','15:40'),
             '10 11 * * 1-5': ('20:10',)}
    if cron not in slots:
        raise ValueError('unknown featured publication schedule')
    local = created_at.astimezone(KST)
    candidates = []
    for offset in range(8):
        date = local.date()-dt.timedelta(days=offset)
        if date.weekday() >= 5: continue
        for slot in slots[cron]:
            target = dt.datetime.combine(date,dt.time.fromisoformat(slot),KST)
            if target <= local: candidates.append(target)
    return max(candidates)


def watch(release, record, read=read_remote, write=publish,
          clock=lambda:dt.datetime.now(KST), pause=time.sleep):
    if release.strftime('%H:%M') not in SLOTS or release.weekday() >= 5:
        raise ValueError('invalid original featured-stock edition')
    if clock() < release-dt.timedelta(minutes=20):
        raise ValueError('edition outside preparation window')
    prefix = release_prefix(release)
    deadline = release+dt.timedelta(minutes=30)
    state = {'releaseAt':release.isoformat(),'state':'waiting_for_draft','startedAt':clock().isoformat(),
             'deadlineAt':deadline.isoformat(),'published':False,'polls':0}
    record(dict(state))
    date,slot = release.strftime('%Y-%m-%d'),release.strftime('%H:%M')
    while True:
        state['polls']+=1
        try:
            root,_=read(prefix+'.json',missing=True)
            day,_=read(prefix+'/'+date+'.json',missing=True)
            indexed,_=read(prefix+'/index.json',missing=True)
            archived=(day or {}).get('editions',{}).get(slot)
            if root and archived and stamp(archived['releaseAt'])==release:
                newer=stamp(root['releaseAt'])>release
                index_ok=index_matches(indexed,root)
                if newer or (root==archived and index_ok):
                    state.update(state='published',published=True,alreadyPublished=True,checkedAt=clock().isoformat())
                    record(dict(state));return state
            if clock()>deadline: break
            draft,_=read('drafts/featured-stocks.json',missing=True)
            if not draft or stamp(draft['releaseAt'])!=release:
                state['lastIssue']='missing_draft_for_original_slot'
            elif clock()<release:
                state['lastIssue']='waiting_for_release_time'
            else:
                try:
                    validate(draft)
                    if not dt.timedelta(0)<=clock()-stamp(draft['asOf'])<=dt.timedelta(minutes=45):
                        raise ValueError('featured-stock research is stale or future')
                    if stamp(draft['reviewedAt'])>clock():
                        raise ValueError('theme review is in the future')
                except (ValueError,KeyError,TypeError) as error:
                    state['lastIssue']='draft_validation_failed: '+str(error)[:400]
                else:
                    if root and stamp(root['releaseAt'])>release:
                        state.update(state='superseded',checkedAt=clock().isoformat())
                        record(dict(state));return state
                    record({**state,'state':'publishing','asOf':draft['asOf']})
                    sha=write(draft)
                    confirmed,_=read(prefix+'.json',sha)
                    archive,_=read(prefix+'/'+date+'.json',sha)
                    index,_=read(prefix+'/index.json',sha)
                    if (confirmed!=draft or archive.get('editions',{}).get(slot)!=draft
                        or not index_matches(index,draft)):
                        raise RuntimeError('featured root/archive/index readback mismatch')
                    state.update(state='published',published=True,commit=sha,asOf=draft['asOf'],checkedAt=clock().isoformat())
                    record(dict(state));return state
        except (urllib.error.URLError,TimeoutError) as error:
            state['lastIssue']=type(error).__name__+': '+str(error)[:400]
            if isinstance(error,urllib.error.HTTPError) and error.code not in (409,422,429,500,502,503,504):
                state.update(state='publication_failed',checkedAt=clock().isoformat())
                record(dict(state));raise
        except Exception as error:
            state.update(state='publication_failed',lastIssue=type(error).__name__+': '+str(error)[:400],checkedAt=clock().isoformat())
            record(dict(state));raise
        if clock()>deadline: break
        pause(min(15,max(0.01,(deadline-clock()).total_seconds())))
    state.update(state='publication_missed',checkedAt=clock().isoformat())
    record(dict(state))
    raise RuntimeError('featured edition missed: '+state.get('lastIssue','started_after_deadline'))


def main():
    if os.environ.get('GITHUB_REPOSITORY')!='KBYOO0815/market-flow-feed':
        raise SystemExit('public feed repository only')
    cron=os.environ.get('EVENT_SCHEDULE')
    if os.environ.get('COLLECTION_HEAD_SHA'):
        request, _ = read_remote('requests/featured-collection.json', os.environ['COLLECTION_HEAD_SHA'])
        if not request or request.get('mode') != 'collect':
            print('published=false: collection probe does not start a publisher')
            return
        release = stamp(request['releaseAt'])
    elif cron:
        # Anchor to workflow creation, so runner queue delays cannot select the next slot.
        created=api('GET','actions/runs/'+os.environ['GITHUB_RUN_ID'])['created_at']
        release=scheduled_release(stamp(created),cron)
    else:
        draft,_=read_remote('drafts/featured-stocks.json',missing=True)
        if not draft:
            print('published=false: no reviewed draft; no code-change publication')
            return
        release=stamp(draft['releaseAt'])
    ident=os.environ['GITHUB_RUN_ID']+'-'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
    path='operations/featured-publications/'+release.strftime('%Y-%m-%d-%H%M')+'/'+ident+'.json'
    result=watch(release,lambda value:save(path,value))
    print('state='+result['state'])


if __name__=='__main__':main()
