"""Deterministic checks for the user's news selection prompt.

Researchers establish event identities, new facts, source reliability and scores.
Code checks those records, windows, ordering and previously published fact keys;
it does not pretend to infer semantic truth from a title or URL.
"""
import copy
import datetime as dt
from functools import reduce
import json
import operator
import pathlib
import sys
from urllib.parse import urlparse

KST = dt.timezone(dt.timedelta(hours=9))
EFFECTIVE = dt.datetime(2026, 11, 13, 11, 50, tzinfo=KST)
ROLE = 'us_theme_summary'
SCORE_KEYS = ('impact', 'certainty', 'novelty', 'koreaRelevance')
SOURCES = {'official', 'filing', 'reuters', 'bloomberg', 'ft_wsj', 'major_media', 'other_reliable'}


def stamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp string required')
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('source timestamp needs timezone')
    return parsed


def https(value):
    parsed = urlparse(value if isinstance(value, str) else '')
    return parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password


def active(payload):
    return stamp(payload['releaseAt']) >= EFFECTIVE


def identity(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('stable event/fact identifier required')
    return value.strip().casefold()


def news(payload):
    return [item for item in payload['items'] if item.get('role') != ROLE]


def priority(item):
    selected = item['selection']
    scores = selected['scores']
    if (type(selected.get('scopeRank')) is not int or selected['scopeRank'] not in (1,2,3,4)
        or set(scores) != set(SCORE_KEYS)
        or any(type(scores[k]) is not int or not 1 <= scores[k] <= 5 for k in SCORE_KEYS)):
        raise ValueError('scope rank 1..4 and four positive 1..5 editorial scores required')
    product = reduce(operator.mul, (scores[k] for k in SCORE_KEYS), 1)
    return (selected['scopeRank'], -product, -stamp(selected['eventAt']).timestamp(), item['id'])


def validate_selection(payload):
    if not active(payload):
        return
    cutoff, release = stamp(payload['asOf']), stamp(payload['releaseAt'])
    window = payload.get('selectionAudit')
    if not isinstance(window, dict) or window.get('mode') not in {'explicit', 'since_previous', 'premarket'}:
        raise ValueError('selectionAudit with actual research window required')
    start, end = stamp(window['startAt']), stamp(window['endAt'])
    if start >= end or end != cutoff:
        raise ValueError('research window must end at actual asOf and start earlier')
    if window['mode'] != 'explicit':
        previous = stamp(window['previousReleaseAt'])
        if previous >= release or stamp(window['previousAsOf']) != start:
            raise ValueError('previous briefing actual cutoff required, not an assumed clock time')
    event_keys, fact_keys = set(), set()
    for item in news(payload):
        selected = item.get('selection')
        if not isinstance(selected, dict):
            raise ValueError('selected event needs source/fact/priority audit')
        event_key = identity(selected.get('eventKey'))
        if event_key in event_keys:
            raise ValueError('same event repeated in this edition; merge new facts into one item')
        event_keys.add(event_key)
        if selected.get('verificationStatus') != 'confirmed' or selected.get('sourceClass') not in SOURCES:
            raise ValueError('rumour, unknown source or unverified event cannot be selected')
        if selected.get('newness') not in {'new', 'followup'}:
            raise ValueError('real new fact or substantive followup required')
        facts = selected.get('facts')
        if not isinstance(facts, list) or not facts:
            raise ValueError('concrete new fact records required')
        fact_times = []
        for fact in facts:
            if not isinstance(fact, dict):
                raise ValueError('fact record must be an object')
            fact_key, occurred = identity(fact.get('key')), stamp(fact['occurredAt'])
            after_start = occurred >= start if window['mode'] == 'explicit' else occurred > start
            if not after_start or occurred > min(end, release):
                raise ValueError('fact outside requested new-material window')
            if not fact.get('statement', '').strip() or not https(fact.get('sourceUrl')):
                raise ValueError('source-backed fact statement required')
            if fact_key in fact_keys:
                raise ValueError('same fact selected more than once, even with different URLs')
            fact_keys.add(fact_key)
            fact_times.append(occurred)
        if stamp(selected['eventAt']) != max(fact_times):
            raise ValueError('eventAt must be the actual latest included new-fact time')
        material = selected.get('materialType')
        if material not in {'event', 'market_trend'}:
            raise ValueError('distinguish a new event from an observed market trend')
        if material == 'market_trend':
            if item.get('kind') != 'market_snapshot' or stamp(item['observedAt']) != stamp(selected['eventAt']):
                raise ValueError('market trend requires matching fresh observation timestamp')
            label = stamp(item['observedAt']).astimezone(KST).strftime('%H:%M KST')
            if label not in item['summary']:
                raise ValueError('market observation time must be visible in summary')
        elif item.get('kind') == 'market_snapshot':
            raise ValueError('market snapshot must be labelled market_trend')
        evidence = selected.get('relatedEvidence', [])
        if not isinstance(evidence, list) or any(not https(e.get('sourceUrl')) for e in evidence):
            raise ValueError('direct business relationship evidence required')
        if set(item['relatedStocks']) != {e.get('stock') for e in evidence}:
            raise ValueError('related stock tags require direct source evidence for every name/code')
        priority(item)
    items = news(payload)
    for region in ('foreign', 'domestic'):
        group = [item for item in items if item['region'] == region]
        if [item['id'] for item in group] != [item['id'] for item in sorted(group, key=priority)]:
            raise ValueError('foreign/domestic importance must be independently sorted by scope and score product')


def validate_history(payload, previous_feeds):
    if not active(payload):
        return
    validate_selection(payload)
    release = stamp(payload['releaseAt'])
    previous_feeds = [feed for feed in previous_feeds if feed and stamp(feed['releaseAt']) < release]
    window = payload['selectionAudit']
    if window['mode'] != 'explicit':
        if not previous_feeds:
            raise ValueError('previous published briefing evidence missing')
        previous = max(previous_feeds, key=lambda feed: stamp(feed['releaseAt']))
        if (stamp(window['previousReleaseAt']) != stamp(previous['releaseAt'])
            or stamp(window['previousAsOf']) != stamp(previous['asOf'])):
            raise ValueError('research window does not match actual previous public briefing')
    old_events, old_facts = set(), set()
    for feed in previous_feeds:
        for item in news(feed):
            selected = item.get('selection') or {}
            if selected.get('eventKey'):
                old_events.add(identity(selected['eventKey']))
            old_facts.update(identity(f['key']) for f in selected.get('facts', []))
    for item in news(payload):
        selected = item['selection']
        if any(identity(f['key']) in old_facts for f in selected['facts']):
            raise ValueError('already published fact repeated; a new URL is not a new fact')
        if identity(selected['eventKey']) in old_events and selected['newness'] != 'followup':
            raise ValueError('existing event must identify substantive followup facts')


def history_for(payload, current, today, reader):
    result = [current] if current else []
    if today:
        result.extend(today.get('editions', {}).values())
    date = stamp(payload['releaseAt']).astimezone(KST).date()
    for days in (1, 2):
        previous, _ = reader('briefings/' + (date-dt.timedelta(days=days)).isoformat() + '.json', missing=True)
        if previous:
            result.extend(previous.get('editions', {}).values())
    return result


def sort_payload(payload):
    result = copy.deepcopy(payload)
    cards = [item for item in result['items'] if item.get('role') == ROLE]
    ordinary = news(result)
    for item in ordinary:
        if item.get('selection', {}).get('materialType') == 'market_trend':
            label = stamp(item['observedAt']).astimezone(KST).strftime('%m/%d %H:%M KST')
            if label not in item['summary']:
                item['summary'] = label + ' 관측. ' + item['summary']
    result['items'] = cards + sorted((i for i in ordinary if i['region'] == 'foreign'), key=priority) + sorted((i for i in ordinary if i['region'] == 'domestic'), key=priority)
    for rank, item in enumerate(result['items'], 1): item['impactRank'] = rank
    validate_selection(result)
    return result


def markdown(payload):
    audit = payload['selectionAudit']
    end = stamp(payload['asOf']).astimezone(KST)
    if audit['mode'] == 'explicit':
        start = stamp(audit['startAt']).astimezone(KST)
        title = end.strftime('%m/%d ') + start.strftime('%H:%M') + '~' + end.strftime('%H:%M') + ' KST 사이에 새로 확인된 재료'
    else:
        title = end.strftime('%m/%d %H:%M KST 기준 재료')
    lines = ['# ' + title]
    for card in (i for i in payload['items'] if i.get('role') == ROLE):
        lines.extend(['', '## ' + card['title'], '', card['summary']])
    for region, heading in [('foreign','국외 신규'), ('domestic','국내 신규')]:
        lines.extend(['', '## '+heading, '', '| 순위 | KST | 신규 재료 | 관련 |', '| -- | -- | -- | -- |'])
        for rank, item in enumerate((i for i in news(payload) if i['region'] == region), 1):
            text = (item['title']+' '+item['summary']).replace('|','\\|').replace('\n',' ')
            linked = '['+text+']('+item['sourceUrl']+')'
            time = stamp(item['selection']['eventAt']).astimezone(KST).strftime('%H:%M')
            lines.append('| '+str(rank)+' | '+time+' | '+linked+' | '+', '.join(item['relatedStocks'])+' |')
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    source, destination = sys.argv[1:3]
    payload = sort_payload(json.loads(pathlib.Path(source).read_text()))
    pathlib.Path(destination).write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n')
    if len(sys.argv) > 3:
        pathlib.Path(sys.argv[3]).write_text(markdown(payload))
