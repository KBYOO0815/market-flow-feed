"""Wait for the original slot's reviewed draft, persist outcomes, never invent news."""
import datetime as dt
import os
import time
import urllib.error
from briefing_schedule import resolve, key
from operation_store import save
from prepare_feed import KST, prepare, timestamp
from publish_feed import read_remote, publish


def watch(release, record, read=read_remote, write=publish,
          clock=lambda: dt.datetime.now(KST), pause=time.sleep):
    deadline = release + dt.timedelta(minutes=30)
    if clock() < release - dt.timedelta(minutes=20):
        raise ValueError('edition not within publication preparation window')
    state = {'releaseAt': release.isoformat(), 'startedAt': clock().isoformat(),
             'deadlineAt': deadline.isoformat(), 'state': 'waiting_for_draft', 'polls': 0}
    record(dict(state))
    while True:
        state['polls'] += 1
        try:
            root, _ = read('morning-briefing.json')
            day, _ = read('briefings/' + release.strftime('%Y-%m-%d') + '.json', missing=True)
            archived = (day or {}).get('editions', {}).get(release.strftime('%H:%M'))
            if (root and archived and timestamp(archived['releaseAt']) == release and
                (root == archived or timestamp(root['releaseAt']) > release)):
                state.update(state='published', alreadyPublished=True, checkedAt=clock().isoformat())
                record(dict(state))
                return state
            if clock() > deadline:
                break
            draft, _ = read('drafts/morning-briefing.json', missing=True)
            if not draft or timestamp(draft['releaseAt']) != release:
                state['lastIssue'] = 'missing_draft_for_original_slot'
            elif clock() < release:
                state['lastIssue'] = 'waiting_for_release_time'
            else:
                try:
                    payload = prepare(draft, clock())
                except (ValueError, KeyError, TypeError) as error:
                    state['lastIssue'] = 'draft_validation_failed: ' + str(error)[:400]
                else:
                    record({**state, 'state': 'publishing', 'asOf': payload['asOf'], 'checkedAt': clock().isoformat()})
                    sha = write(payload)
                    if not sha:
                        state.update(state='superseded', checkedAt=clock().isoformat())
                        record(dict(state))
                        return state
                    confirmed, _ = read('morning-briefing.json', sha)
                    archive, _ = read('briefings/' + release.strftime('%Y-%m-%d') + '.json', sha)
                    if confirmed != payload or archive.get('editions', {}).get(release.strftime('%H:%M')) != payload:
                        raise RuntimeError('publication readback mismatch')
                    state.update(state='published', commit=sha, asOf=payload['asOf'],
                                 itemCount=len(payload['items']), checkedAt=clock().isoformat())
                    record(dict(state))
                    return state
        except (urllib.error.URLError, TimeoutError) as error:
            state['lastIssue'] = type(error).__name__ + ': ' + str(error)[:400]
            if isinstance(error, urllib.error.HTTPError) and error.code not in (429, 500, 502, 503, 504):
                state.update(state='publication_failed', checkedAt=clock().isoformat())
                record(dict(state))
                raise
        except Exception as error:
            state.update(state='publication_failed', lastIssue=type(error).__name__ + ': ' + str(error)[:400], checkedAt=clock().isoformat())
            record(dict(state))
            raise
        if clock() > deadline:
            break
        pause(min(15, max(0.01, (deadline - clock()).total_seconds())))
    state.update(state='publication_missed', checkedAt=clock().isoformat())
    record(dict(state))
    raise RuntimeError('No publishable draft for original slot before deadline: ' + state.get('lastIssue', 'run_started_after_deadline'))


def main():
    if os.environ.get('GITHUB_REPOSITORY') != 'KBYOO0815/market-flow-feed':
        raise SystemExit('public data repo only')
    cron = os.environ.get('EVENT_SCHEDULE')
    if cron:
        release = resolve(dt.datetime.now(KST), cron)
    else:
        draft, _ = read_remote('drafts/morning-briefing.json', missing=True)
        if not draft:
            raise ValueError('manual/push publication requires an explicit reviewed draft')
        release = resolve(dt.datetime.now(KST), release_at=draft['releaseAt'])
    ident = os.environ['GITHUB_RUN_ID'] + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    path = 'operations/publications/' + key(release) + '/' + ident + '.json'
    state = watch(release, lambda value: save(path, value))
    print('state=' + state['state'])


if __name__ == '__main__':
    main()
