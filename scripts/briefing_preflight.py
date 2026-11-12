"""Collect bounded source evidence. Availability NEVER certifies editorial coverage."""
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from briefing_schedule import resolve, key
from operation_store import save
from prepare_feed import KST


class Links(HTMLParser):
    def __init__(self, url):
        super().__init__()
        self.url, self.current, self.text, self.links = url, None, [], {}
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.current, self.text = dict(attrs).get('href', ''), []
    def handle_data(self, data):
        if self.current is not None:
            self.text.append(data)
    def handle_endtag(self, tag):
        if tag != 'a' or self.current is None:
            return
        href = self.current
        report = re.search(r'(?:rcpNo=|openReport\([\'\"])(\d{14})', href)
        url = ('https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + report[1]
               if report else urllib.parse.urljoin(self.url, href))
        title = ' '.join(' '.join(self.text).split())[:180]
        if (url.startswith('https://') and len(title) >= 8 and
            re.search(r'/view/AKR|rcpNo=|/news/|/pressreleases/|/no01010[12]/|news\.samsung\.com/kr/', url)):
            self.links.setdefault(url, {'title': title, 'sourceUrl': url, 'verified': False})
        self.current = None


def fetch_source(url, date, opener=urllib.request.urlopen, pause=time.sleep, clock=lambda: dt.datetime.now(KST)):
    record = {'sourceUrl': url, 'attempts': [], 'candidates': [], 'available': False}
    for attempt in range(2):
        entry = {'checkedAt': clock().isoformat()}
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'MarketFlow-SourceCheck/1.0', 'Cache-Control': 'no-cache'})
            with opener(request, timeout=10) as response:
                body = response.read(2_000_001)
                entry.update(httpStatus=response.status, responseDate=response.headers.get('Date'), cacheAge=response.headers.get('Age'))
                if len(body) > 2_000_000:
                    raise ValueError('source exceeds bounded response size')
                charset = response.headers.get_content_charset() or 'utf-8'
                html = body.decode(charset, errors='replace')
            record['contentSha256'] = hashlib.sha256(body).hexdigest()
            if 'dart.fss.or.kr/dsac001/' in url:
                text = re.sub(r'<[^>]+>', ' ', html)
                selected = re.search(r'전체\s*([\d,]+)\s*건\s*\(\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', text)
                if not selected:
                    raise ValueError('DART selected date/count unavailable; cannot infer empty filings')
                selected_date = dt.date(*map(int, selected.group(2, 3, 4)))
                record.update(selectedDate=selected_date.isoformat(), filingCount=int(selected[1].replace(',', '')))
                if selected_date != date:
                    raise ValueError('DART stale selected date: ' + selected_date.isoformat())
            parser = Links(url)
            parser.feed(html)
            record.update(available=True, candidates=list(parser.links.values())[:30])
            record['attempts'].append(entry)
            return record
        except Exception as error:
            entry.update(errorType=type(error).__name__, error=str(error)[:400])
            if isinstance(error, urllib.error.HTTPError):
                entry['httpStatus'] = error.code
            record['attempts'].append(entry)
            # Do not retry access denials. Continue to the independent fallback.
            if isinstance(error, urllib.error.HTTPError) and error.code not in (429, 500, 502, 503, 504):
                break
            if attempt == 0:
                pause(1)
    return record


def sources(date):
    return {
        'foreign_market': ['https://www.yna.co.kr/market-plus/global-market', 'https://www.reuters.com/markets/us/'],
        'foreign_policy': ['https://www.federalreserve.gov/newsevents/pressreleases.htm', 'https://www.yna.co.kr/international/all'],
        'foreign_technology': ['https://nvidianews.nvidia.com/news', 'https://news.samsung.com/global/'],
        'domestic_disclosures': ['https://dart.fss.or.kr/dsac001/mainAll.do?selectDate=' + date.strftime('%Y.%m.%d'), 'https://kind.krx.co.kr/'],
        'domestic_policy': ['https://www.fsc.go.kr/no010101', 'https://www.motie.go.kr/'],
        'domestic_market': ['https://kind.krx.co.kr/common/stockschedule.do?method=StockScheduleMain',
            'https://open.krx.co.kr/contents/MKD/01/0110/01100305/MKD01100305.jsp',
            'https://atsview.com/calendar/' + str(date.year)]
    }


def collect(release, fetch=fetch_source):
    def topic(pair):
        name, urls = pair
        # Keep all results, including failures, instead of cancelling other fields.
        return name, [fetch(url, release.date()) for url in urls]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = dict(pool.map(topic, sources(release.date()).items()))
    unavailable = [name for name, rows in results.items() if not any(r['available'] for r in rows)]
    candidates = {c['sourceUrl']: c for rows in results.values() for row in rows for c in row['candidates']}
    return {'state': 'source_checks_partial' if unavailable else 'source_checks_collected',
        'releaseAt': release.isoformat(), 'checkedAt': dt.datetime.now(KST).isoformat(),
        'editorialCoverageVerified': False, 'tradingDayVerified': False,
        'requiresEditorialReview': True, 'unavailableTopics': unavailable,
        'sources': results, 'candidates': list(candidates.values()),
        'note': 'HTTP success and link collection are not fact verification or trading-day confirmation.'}


def main():
    if os.environ.get('GITHUB_REPOSITORY') != 'KBYOO0815/market-flow-feed':
        raise SystemExit('public data repo only')
    request = json.loads(pathlib.Path('requests/briefing-preflight.json').read_text()) if os.environ.get('GITHUB_EVENT_NAME') == 'push' else {}
    release = resolve(dt.datetime.now(KST), os.environ.get('EVENT_SCHEDULE'), os.environ.get('RELEASE_AT') or request.get('releaseAt'), preflight=True)
    now = dt.datetime.now(KST)
    if not release - dt.timedelta(minutes=30) <= now <= release + dt.timedelta(minutes=30):
        raise ValueError('source check outside original edition window; refusing relabel')
    ident = os.environ['GITHUB_RUN_ID'] + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    path = 'operations/source-checks/' + key(release) + '/' + ident + '.json'
    save(path, {'state': 'checking_sources', 'releaseAt': release.isoformat(), 'startedAt': now.isoformat(), 'editorialCoverageVerified': False})
    result = collect(release)
    save(path, result)
    save('operations/source-checks/' + key(release) + '.json', {'releaseAt': release.isoformat(), 'checkedAt': result['checkedAt'], 'state': result['state'], 'evidencePath': path, 'editorialCoverageVerified': False})
    print(result['state'], 'unavailableTopics=', result['unavailableTopics'], 'candidates=', len(result['candidates']))


if __name__ == '__main__':
    main()
