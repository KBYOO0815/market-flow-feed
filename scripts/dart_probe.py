"""Prints real DART responses so templates can be written against them. Writes nothing."""
import datetime, json
from dart_news_test import document, get

TREASURY = {'자기주식취득결정': 'tsstkAqDecsn', '자기주식취득신탁계약체결결정': 'tsstkAqTrctrCnsDecsn'}

def listing(bgn, end):
    rows, page = [], 1
    while True:
        d = json.loads(get('list.json', bgn_de=bgn, end_de=end, page_count=100, page_no=page))
        if d['status'] != '000':
            return rows
        rows += d['list']
        if page >= d['total_page'] or page >= 60:
            return rows
        page += 1

today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date()
rows = listing((today - datetime.timedelta(days=20)).strftime('%Y%m%d'), today.strftime('%Y%m%d'))
print('listed', len(rows))
for key, api in TREASURY.items():
    hits = [r for r in rows if key in r['report_nm']]
    print(key, 'count', len(hits), 'names', sorted({r['report_nm'].strip() for r in hits}))
    for r in hits[:3]:
        d = json.loads(get(api + '.json', corp_code=r['corp_code'], bgn_de=r['rcept_dt'], end_de=r['rcept_dt']))
        print('API', api, r['rcept_no'], d.get('status'), json.dumps(d.get('list'), ensure_ascii=False))
hits = [r for r in rows if '배당결정' in r['report_nm']]
print('배당결정 count', len(hits), 'names', sorted({' '.join(r['report_nm'].split()) for r in hits}))
shown = 0
for r in hits:
    text = document(r['rcept_no'])
    if text:
        print('DOC', r['rcept_no'], r['corp_name'], ' '.join(r['report_nm'].split()), '::', text[:1500])
        shown += 1
    if shown == 5:
        break
