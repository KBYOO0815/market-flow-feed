"""Publish root and dated editions atomically, preserving concurrent main updates."""
import base64
import datetime as dt
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request
from prepare_feed import KST, prepare, timestamp, validate

REPO = 'KBYOO0815/market-flow-feed'


def api(method, path, body=None):
    url = 'https://api.github.com/repos/' + REPO + '/' + path
    headers = {'Authorization': 'Bearer ' + os.environ['PUBLISH_TOKEN'], 'Content-Type': 'application/json', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def read_remote(path, ref='main', missing=False):
    try:
        obj = api('GET', 'contents/' + path + '?ref=' + ref)
        return json.loads(base64.b64decode(obj['content'])), obj['sha']
    except urllib.error.HTTPError as error:
        if error.code == 404 and missing:
            return None, None
        raise


def archive_update(payload, previous):
    release = timestamp(payload['releaseAt']).astimezone(KST)
    date, slot = release.strftime('%Y-%m-%d'), release.strftime('%H:%M')
    if previous is not None and previous.get('date') != date:
        raise ValueError('Archive date mismatch; refusing to overwrite another day.')
    day = {'date': date, 'editions': dict((previous or {}).get('editions', {}))}
    day['editions'][slot] = payload
    day['editions'] = dict(sorted(day['editions'].items()))
    return 'briefings/' + date + '.json', day


def expired_archive_paths(tree, release):
    # Keep the release date and the preceding two calendar dates (KST).
    today = timestamp(release).astimezone(KST).date()
    cutoff = today - dt.timedelta(days=2)
    paths = []
    for node in tree.get('tree', []):
        path = node.get('path', '')
        if re.fullmatch(r'briefings/\d{4}-\d{2}-\d{2}\.json', path):
            if dt.date.fromisoformat(path[10:20]) < cutoff:
                paths.append(path)
    return paths


def publish(payload):
    for attempt in range(3):
        # Pin every read to the same head. A non-fast-forward ref update fails
        # rather than dropping a concurrently staged draft or another edition.
        head = api('GET', 'git/ref/heads/main')['object']['sha']
        commit = api('GET', 'git/commits/' + head)
        current, _ = read_remote('morning-briefing.json', head)
        if timestamp(current['releaseAt']) > timestamp(payload['releaseAt']) or timestamp(current['asOf']) > timestamp(payload['asOf']):
            return None
        existing_tree = api('GET', 'git/trees/' + commit['tree']['sha'] + '?recursive=1')
        expired = expired_archive_paths(existing_tree, payload['releaseAt'])
        path, _ = archive_update(payload, None)
        previous, _ = read_remote(path, head, missing=True)
        path, day = archive_update(payload, previous)
        if current == payload and previous == day and not expired:
            return head
        entries = [{'path': name, 'mode': '100644', 'type': 'blob', 'content': json.dumps(body, ensure_ascii=False, indent=2) + '\n'}
                   for name, body in [('morning-briefing.json', payload), (path, day)]]
        entries.extend({'path': old, 'mode': '100644', 'type': 'blob', 'sha': None} for old in expired)
        tree = api('POST', 'git/trees', {'base_tree': commit['tree']['sha'], 'tree': entries})
        new = api('POST', 'git/commits', {'message': 'Publish and archive reviewed briefing ' + payload['releaseAt'], 'tree': tree['sha'], 'parents': [head]})
        try:
            api('PATCH', 'git/refs/heads/main', {'sha': new['sha'], 'force': False})
        except urllib.error.HTTPError as error:
            if error.code not in (409, 422) or attempt == 2:
                raise
            continue
        confirmed, _ = read_remote('morning-briefing.json', new['sha'])
        archived, _ = read_remote(path, new['sha'])
        if confirmed != payload or archived != day:
            raise RuntimeError('Published root/archive readback does not match.')
        return new['sha']
    raise RuntimeError('Concurrent publication could not be resolved.')


def output(value):
    print(value)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write(value + '\n')


def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO:
        raise SystemExit('This publisher is scoped to the public data repository only.')
    path = pathlib.Path('drafts/morning-briefing.json')
    if not path.exists():
        output('published=false')
        print('No reviewed draft staged; existing public data is not relabelled.')
        return
    draft = validate(json.loads(path.read_text()))
    if draft.get('correction'):
        # Historical correction was already applied and verified separately.
        # A scheduled job must NEVER replay or roll back a corrected edition.
        current, _ = read_remote('morning-briefing.json')
        correction_release = timestamp(draft['releaseAt']).astimezone(KST)
        correction_path = 'briefings/' + correction_release.strftime('%Y-%m-%d') + '.json'
        existing, _ = read_remote(correction_path)
        slot = correction_release.strftime('%H:%M')
        if current == draft and existing.get('editions', {}).get(slot) == draft:
            output('published=false')
            print('Historical correction already published and archived; no scheduled replay.')
            return
        raise ValueError('Historical correction requires separately reviewed publication; refusing scheduled replay.')
    release, now = timestamp(draft['releaseAt']), dt.datetime.now(KST)
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
    draft, _ = read_remote('drafts/morning-briefing.json')
    payload = prepare(draft, dt.datetime.now(KST))
    sha = publish(payload)
    output('published=' + ('true' if sha else 'false'))
    if sha:
        output('commit=' + sha)
    else:
        print('A newer briefing is already public; refusing rollback.')


if __name__ == '__main__':
    main()
