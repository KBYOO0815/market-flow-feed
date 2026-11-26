"""Builds market-news-test.json from DART. No AI. Never touches market-news.json."""
import datetime, json
from dart_news_test import KEYWORDS, contract, document, listing

OUTPUT = 'market-news-test.json'
SLOTS = ['07:40', '11:40', '15:40', '19:40', '22:40']
LIMIT = 10  # the app shows at most 10 domestic items

def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).replace(microsecond=0)
    passed = [s for s in SLOTS if s <= now.strftime('%H:%M')]
    if not passed:
        raise SystemExit('no news slot has passed yet today')
    slot, date = passed[-1], now.strftime('%Y-%m-%d')

    picked, seen = [], set()
    for row in listing(now.strftime('%Y%m%d')):
        report = ' '.join(row['report_nm'].split())
        key = (row['corp_code'], report)
        if any(k in report for k in KEYWORDS) and key not in seen:
            seen.add(key)
            picked.append((row, report))

    written, linked = [], []
    for row, report in picked:
        company, number = row['corp_name'], row['rcept_no']
        url = f'https://dart.fss.or.kr/dsaf001/main.do?rcpNo={number}'
        made = None
        if '단일판매' in report:
            text = document(number)
            made = contract(company, report, text) if text else None
        item = {
            'id': f'dart-{number}', 'region': 'domestic', 'category': '국내공시',
            'title': made[0] if made else f'{company}, {report}',
            'summary': made[1] if made else f'DART 원문 확인: {url}',
            'publishedAt': f'{date}T00:00:00+09:00', 'publishedAtPrecision': 'date',
            'checkedAt': now.isoformat(), 'sourceName': '금융감독원 DART', 'sourceUrl': url,
            'relatedStocks': [company], 'generatedBy': 'code' if made else 'link',
        }
        (written if made else linked).append(item)

    items = (written + linked)[:LIMIT]
    for rank, item in enumerate(items, 1):
        item['impactRank'] = rank
    feed = {
        'schemaVersion': 1, 'test': True, 'updatedAt': now.isoformat(),
        'navigation': {'previous': [], 'today': [{'date': date, 'slot': slot, 'state': 'published'}], 'next': []},
        'days': [{'date': date, 'isKrxTradingDay': True, 'displaySlots': [slot], 'sessions': [{
            'slot': slot, 'asOf': now.isoformat(), 'publishedAt': now.isoformat(),
            'foreignNews': [], 'domesticNews': items, 'usThemes': [], 'researchStatus': 'partial',
        }]}],
    }
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'matched={len(picked)} written_by_code={len(written)} link_only={len(linked)} saved={len(items)} slot={date} {slot}')

if __name__ == '__main__':
    main()
