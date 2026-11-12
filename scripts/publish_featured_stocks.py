"""Publish reviewed featured stocks atomically; never overwrite briefing data."""
import datetime as dt
import os
import re
import time
import urllib.error
from featured_stocks import KST, archive, retained_dates, stamp, validate
from publish_feed import REPO, api, output, read_remote
import json


def publication_entries(payload, day, dates):
    date = stamp(payload['releaseAt']).date()
    visible = retained_dates(dates, date, 2)
    index = {'schemaVersion': 1, 'asOf': payload['asOf'], 'releaseAt': payload['releaseAt'],
             'appVisibleCalendarDays': 2,
             'visibleUntil': dt.datetime.combine(date + dt.timedelta(days=2), dt.time(), KST).isoformat(),
             'dates': [{'date': d, 'path': 'featured-stocks/' + d + '.json'} for d in reversed(visible)]}
    content = [('featured-stocks.json', payload),
               ('featured-stocks/' + date.isoformat() + '.json', day),
               ('featured-stocks/index.json', index)]
    entries = [{'path': p, 'mode': '100644', 'type': 'blob',
                'content': json.dumps(body, ensure_ascii=False, indent=2) + '\n'} for p, body in content]
    retained = retained_dates(dates, date, 3)
    entries.extend({'path': 'featured-stocks/' + old + '.json', 'mode': '100644', 'type': 'blob', 'sha': None}
                   for old in dates if old not in retained and dt.date.fromisoformat(old) < date)
    return entries, index


def publish(payload):
    for attempt in range(3):
        head = api('GET', 'git/ref/heads/main')['object']['sha']
        commit = api('GET', 'git/commits/' + head)
        current, _ = read_remote('featured-stocks.json', head, missing=True)
        if current and (stamp(current['releaseAt']) > stamp(payload['releaseAt']) or stamp(current['asOf']) > stamp(payload['asOf'])):
            raise ValueError('refusing featured-stocks rollback')
        tree = api('GET', 'git/trees/' + commit['tree']['sha'] + '?recursive=1')
        dates = [n['path'][16:26] for n in tree['tree'] if re.fullmatch(r'featured-stocks/\d{4}-\d{2}-\d{2}\.json', n['path'])]
        date = stamp(payload['releaseAt']).date().isoformat()
        path = 'featured-stocks/' + date + '.json'
        previous, _ = read_remote(path, head, missing=True)
        day = archive(payload, previous)
        entries, index = publication_entries(payload, day, sorted(set(dates + [date])))
        new_tree = api('POST', 'git/trees', {'base_tree': commit['tree']['sha'], 'tree': entries})
        new = api('POST', 'git/commits', {'message': 'Publish featured stocks ' + payload['releaseAt'],
                                       'tree': new_tree['sha'], 'parents': [head]})
        try:
            api('PATCH', 'git/refs/heads/main', {'sha': new['sha'], 'force': False})
        except urllib.error.HTTPError as error:
            if error.code not in (409, 422) or attempt == 2:
                raise
            continue
        for name, expected in [('featured-stocks.json', payload), (path, day), ('featured-stocks/index.json', index)]:
            actual, _ = read_remote(name, new['sha'])
            if actual != expected:
                raise RuntimeError('featured-stocks readback mismatch: ' + name)
        return new['sha']
    raise RuntimeError('concurrent featured-stocks publication failed')


def missed(reason):
    output('published=false')
    print(reason)
    if os.environ.get('GITHUB_EVENT_NAME') == 'schedule':
        raise RuntimeError('Scheduled featured stocks MISSED: ' + reason)


def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO:
        raise SystemExit('publisher is limited to the public feed repository')
    payload, _ = read_remote('drafts/featured-stocks.json', missing=True)
    if payload is None:
        missed('No reviewed featured-stocks draft is available.')
        return
    validate(payload)
    release, now = stamp(payload['releaseAt']), dt.datetime.now(KST)
    if now > release + dt.timedelta(minutes=30) or release - now > dt.timedelta(minutes=20):
        missed('Draft is outside this publication window; releaseAt=' + payload['releaseAt'])
        return
    if now < release:
        time.sleep((release - now).total_seconds())
    # A new draft may have arrived while this job was waiting. Never publish
    # a different edition before its time.
    refreshed, _ = read_remote('drafts/featured-stocks.json')
    if refreshed != payload:
        raise ValueError('draft changed during publication wait; use the new run')
    now = dt.datetime.now(KST)
    if not release <= now <= release + dt.timedelta(minutes=30) or now - stamp(payload['asOf']) > dt.timedelta(minutes=45):
        raise ValueError('featured-stocks edition is stale')
    sha = publish(payload)
    output('published=true')
    output('commit=' + sha)


if __name__ == '__main__':
    main()

