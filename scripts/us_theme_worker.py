"""Persist genuine source snapshots independently from editorial news publication."""
import datetime as dt
import json
import os
import pathlib
from briefing_schedule import key
from operation_store import save
from us_themes import KST, collect_snapshot, stamp


def run(release_at, ident, probe=False, collector=collect_snapshot, persist=save):
    release = stamp(release_at).astimezone(KST)
    path = 'operations/us-theme-sources/' + key(release) + '/' + ident + '.json'
    result = {'state': 'collecting', 'releaseAt': release.isoformat(),
        'checkedAt': dt.datetime.now(KST).isoformat(), 'publishable': False}
    persist(path, dict(result))
    try:
        result = collector(release.isoformat(), probe=probe)
    except Exception as error:
        result.update(state='collection_failed', checkedAt=dt.datetime.now(KST).isoformat(),
                      errorType=type(error).__name__, error=str(error)[:800])
    persist(path, result)
    if not probe:
        persist('operations/us-theme-sources/' + key(release) + '.json',
            {'releaseAt': release.isoformat(), 'state': result['state'], 'evidencePath': path,
             'checkedAt': result.get('collectedAt') or result.get('checkedAt'), 'publishable': result.get('publishable', False)})
    return result


if __name__ == '__main__':
    if os.environ.get('GITHUB_REPOSITORY') != 'KBYOO0815/market-flow-feed':
        raise SystemExit('public data repo only')
    request = json.loads(pathlib.Path('requests/us-theme-probe.json').read_text())
    result = run(request['releaseAt'], os.environ['GITHUB_RUN_ID']+'-'+os.environ.get('GITHUB_RUN_ATTEMPT', '1'), probe=True)
    print('probeOnly=true state=' + result['state'] + ' stocks=' + str(len(result.get('stocks', []))))
    if result['state'] != 'collected':
        raise SystemExit(result.get('error', 'collection failed'))
