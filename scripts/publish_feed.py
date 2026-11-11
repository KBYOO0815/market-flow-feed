"""Promote a reviewed draft at its KST release slot with a contents-SHA lease."""
import base64
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from prepare_feed import KST, check_release, prepare, timestamp, validate

REPO = 'KBYOO0815/market-flow-feed'

def api(method, path, body=None):
    url = 'https://api.github.com/repos/' + REPO + '/contents/' + path
    headers = {'Authorization': 'Bearer ' + os.environ['PUBLISH_TOKEN'], 'Content-Type': 'application/json', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

def read_remote(path):
    obj = api('GET', path)
    return json.loads(base64.b64decode(obj['content'])), obj['sha']

def output(value):
    print(value)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write(value + '\n')

def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO:
        raise SystemExit('This publisher is scoped to the public data repository only.')
    draft_path = pathlib.Path('drafts/morning-briefing.json')
    if not draft_path.exists():
        output('published=false')
        print('No reviewed draft staged; existing public data is not relabelled.')
        return
    draft = validate(json.loads(draft_path.read_text()))
    release = timestamp(draft['releaseAt'])
    now = dt.datetime.now(KST)
    if timestamp(draft['asOf']) > now + dt.timedelta(minutes=1):
        raise ValueError('Research timestamp is in the future; do not manufacture a current review.')
    wait = (release - now).total_seconds()
    if wait > 1200 or now > release + dt.timedelta(minutes=30):
        output('published=false')
        print('Draft is outside this publication window; no stale publication.')
        return
    if wait > 0:
        print('Waiting for approved releaseAt:', draft['releaseAt'], flush=True)
        time.sleep(wait)
    # The draft may have been refreshed while this job waited.
    draft, _ = read_remote('drafts/morning-briefing.json')
    payload = prepare(draft, dt.datetime.now(KST))
    encoded = base64.b64encode((json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode()).decode()
    for attempt in range(3):
        current, sha = read_remote('morning-briefing.json')
        if timestamp(current['releaseAt']) > timestamp(payload['releaseAt']) or timestamp(current['asOf']) > timestamp(payload['asOf']):
            output('published=false')
            print('A newer briefing is already public; refusing rollback.')
            return
        if current == payload:
            output('published=true')
            print('Identical reviewed briefing is already public.')
            return
        try:
            result = api('PUT', 'morning-briefing.json', {'message': 'Publish reviewed briefing ' + payload['releaseAt'], 'content': encoded, 'sha': sha, 'branch': 'main'})
            confirmed, _ = read_remote('morning-briefing.json')
            if confirmed != payload:
                raise RuntimeError('Publication readback does not match; do not report success.')
            output('published=true')
            output('commit=' + result['commit']['sha'])
            return
        except urllib.error.HTTPError as error:
            if error.code not in (409, 422) or attempt == 2:
                raise
    raise RuntimeError('Publication lease could not be acquired.')

if __name__ == '__main__':
    main()
