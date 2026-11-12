import copy
import datetime as dt
import unittest
from unittest.mock import patch
import publish_featured_stocks as publisher
from featured_stocks import KST, SLOTS, archive, collect, enrich, retained_dates, validate, weighted
from publish_featured_stocks import publication_entries


def fixture():
    stocks = []
    for i in range(50):
        quotes = {m: {'observedAt': '2026-11-12T09:30:00+09:00', 'sourceUrl': 'https://stock.naver.com/quote/' + m} for m in ('KRX', 'NXT')}
        stocks.append({'code': f'{i:06}', 'name': 'fixture', 'turnoverRank': i + 1,
                       'krxTradeAmount': 1000 - i, 'nxtTradeAmount': 100,
                       'integratedTradeAmount': 1100 - i, 'changeRate': 5.0 - i,
                       'rateMarket': 'KRX', 'quotes': quotes, 'zeroNxtEvidence': None})
    return {'schemaVersion': 1, 'asOf': '2026-11-12T09:31:00+09:00',
            'collectionStartedAt': '2026-11-12T09:30:00+09:00',
            'releaseAt': '2026-11-12T09:40:00+09:00', 'tradingDayVerified': True,
            'calendarSourceUrl': 'https://global.krx.co.kr/calendar',
            'amountUnit': 'KRW', 'rateBasis': 'KRX_PREVIOUS_CLOSE',
            'stocks': stocks, 'byTurnover': [s['code'] for s in stocks],
            'byChangeRate': [s['code'] for s in stocks], 'themes': [],
            'sourceRecords': [{'market': m, 'sourceUrl': 'https://stock.naver.com/' + m,
                               'retrievedAt': '2026-11-12T09:30:00+09:00'} for m in ('KRX','NXT')],
            'unclassified': [s['code'] for s in stocks]}


def reviewed():
    return {'reviewedAt': '2026-11-12T09:35:00+09:00', 'themes': [
        {'id': 'example', 'name': '예시', 'stockCodes': ['000000','000001'],
         'membershipEvidence': [{'code': f'{i:06}', 'sourceUrl': 'https://example.com/ir', 'fact': 'fixture'} for i in range(2)],
         'reason': None}]}


class FeaturedStocksTests(unittest.TestCase):
    def test_scheduled_missing_draft_is_failure_not_false_success(self):
        with patch.dict(publisher.os.environ, {'GITHUB_REPOSITORY': publisher.REPO, 'GITHUB_EVENT_NAME': 'schedule'}), patch.object(publisher, 'read_remote', return_value=(None,None)):
            with self.assertRaisesRegex(RuntimeError, 'MISSED'):
                publisher.main()

    def test_push_without_draft_remains_safe_no_op(self):
        with patch.dict(publisher.os.environ, {'GITHUB_REPOSITORY': publisher.REPO, 'GITHUB_EVENT_NAME': 'push'}), patch.object(publisher, 'read_remote', return_value=(None,None)), patch.object(publisher, 'publish') as publish:
            publisher.main()
            publish.assert_not_called()

    def test_scheduled_stale_draft_reports_missed(self):
        with patch.dict(publisher.os.environ, {'GITHUB_EVENT_NAME': 'schedule'}):
            with self.assertRaisesRegex(RuntimeError, 'MISSED'):
                publisher.missed('stale draft')

    def test_weighted_not_simple_mean_and_decliners_count(self):
        self.assertEqual(weighted([{'changeRate': 10, 'integratedTradeAmount': 100},
                                   {'changeRate': -10, 'integratedTradeAmount': 900}]), -8.0)

    def test_two_orders_share_exactly_fifty(self):
        p = enrich(fixture(), reviewed())
        self.assertEqual(len(p['unclassified']), 48)
        self.assertEqual(set(p['byTurnover']), set(p['byChangeRate']))
        p['byChangeRate'][0], p['byChangeRate'][1] = p['byChangeRate'][1], p['byChangeRate'][0]
        with self.assertRaisesRegex(ValueError, 'rate order'):
            validate(p)

    def test_membership_duplicate_rejected(self):
        r = reviewed()
        r['themes'].append(copy.deepcopy(r['themes'][0]))
        with self.assertRaises(ValueError):
            enrich(fixture(), r)

    def test_future_reason_rejected(self):
        r = reviewed()
        r['themes'][0]['reason'] = {'summary': 'fixture', 'sourceUrl': 'https://example.com/news',
            'publishedAt': '2026-11-12T09:41:00+09:00', 'checkedAt': r['reviewedAt'], 'causality': 'related_fact_only'}
        with self.assertRaisesRegex(ValueError, 'reason publication'):
            enrich(fixture(), r)

    def test_retention_calendar_not_trading_days(self):
        dates = ['2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12']
        today = dt.date(2026,11,12)
        self.assertEqual(retained_dates(dates, today, 3), dates[1:])
        self.assertEqual(retained_dates(dates, today, 2), dates[2:])
        self.assertEqual(retained_dates(dates, dt.date(2026,11,15), 2), [])

    def test_publisher_prunes_only_featured_dates(self):
        p = enrich(fixture(), reviewed())
        day = archive(p)
        entries, index = publication_entries(p, day, ['2026-11-09','2026-11-10','2026-11-11','2026-11-12'])
        self.assertEqual([x['path'] for x in entries if 'sha' in x], ['featured-stocks/2026-11-09.json'])
        self.assertEqual([x['date'] for x in index['dates']], ['2026-11-12','2026-11-11'])
        self.assertFalse(any('briefing' in x['path'] for x in entries))

    def test_archive_preserves_other_editions(self):
        p = enrich(fixture(), reviewed())
        first = archive(p)
        q = copy.deepcopy(p)
        q['releaseAt'] = '2026-11-12T11:40:00+09:00'
        result = archive(q, first)
        self.assertEqual(set(result['editions']), {'09:40','11:40'})
        self.assertEqual(result['editions']['09:40'], p)

    def test_all_five_slots(self):
        self.assertEqual(SLOTS, ('09:40','11:40','13:40','15:40','20:10'))

    def test_404_never_becomes_zero(self):
        import urllib.error
        krx = [{'itemcode': f'{i:06}', 'type': 'ST', 'tradeAmount': str(100000-i)} for i in range(1100)]
        nxt = [{'itemcode': f'{i:06}', 'type': 'ST', 'tradeAmount': str(1000-i)} for i in range(100,200)]
        def fetch(url):
            if 'tradeType=KRX' in url:
                return krx
            if 'tradeType=NXT' in url:
                return nxt
            raise urllib.error.HTTPError(url,404,'Not Found',{},None)
        with self.assertRaisesRegex(ValueError, '404 is not zero'):
            collect('2026-11-12T09:40:00+09:00', {'date':'2026-11-12','tradingDayVerified':True,
                    'calendarSourceUrl':'https://global.krx.co.kr/calendar'}, fetch=fetch,
                    now=dt.datetime(2026,11,12,9,30,tzinfo=KST))

    def test_stale_and_incomplete_fail(self):
        p = enrich(fixture(), reviewed())
        p['stocks'][0]['quotes']['NXT']['observedAt'] = '2026-11-11T09:30:00+09:00'
        with self.assertRaises(ValueError):
            validate(p)
        p = enrich(fixture(), reviewed())
        p['stocks'].pop()
        with self.assertRaises(ValueError):
            validate(p)


if __name__ == '__main__':
    unittest.main()

