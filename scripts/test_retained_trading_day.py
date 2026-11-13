import copy
import datetime as dt
import unittest
from trading_day_evidence import KST, KIND_QUOTE, NAVER_QUOTE, reuse_same_day

class RetainedTradingDayEvidence(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 11, 13, 20, 30, tzinfo=KST)
        self.proof = {'verified': True, 'calendarSourceUrl': KIND_QUOTE, 'sources': [
            {'sourceUrl': url, 'market': 'KRX', 'code': '005930', 'date': '2026-11-13',
             'observedAt': '2026-11-13T15:30:00+09:00',
             'checkedAt': '2026-11-13T17:05:00+09:00',
             'tradeVolume': 100, 'tradeAmount': 1000, 'kind': 'actual_krx_trade'}
            for url in (KIND_QUOTE, NAVER_QUOTE)]}
    def test_after_close_reuses_evidence_without_changing_observation_times(self):
        before = copy.deepcopy(self.proof)
        result = reuse_same_day(self.proof, self.now.date(), self.now)
        self.assertEqual(result['sources'], before['sources'])
        self.assertEqual(self.proof, before)
        self.assertEqual(result['evidenceUse'], 'same_day_trading_calendar_only')
    def test_rejects_other_day_missing_source_zero_wrong_market_and_future(self):
        for field, value in [('date', '2026-11-12'), ('tradeVolume', 0),
                             ('tradeAmount', 0), ('tradeVolume', True),
                             ('sourceUrl', 'https://example.com'), ('market', 'NXT'),
                             ('observedAt', '2026-11-13T21:00:00+09:00'),
                             ('checkedAt', '2026-11-13T21:00:00+09:00')]:
            with self.subTest(field=field, value=value):
                proof = copy.deepcopy(self.proof)
                proof['sources'][1][field] = value
                self.assertIsNone(reuse_same_day(proof, self.now.date(), self.now))
        self.assertIsNone(reuse_same_day(self.proof, self.now.date()+dt.timedelta(days=1), self.now))
    def test_rejects_unverified_or_single_source(self):
        self.proof['verified'] = False
        self.assertIsNone(reuse_same_day(self.proof, self.now.date(), self.now))
        self.proof['verified'] = True
        self.proof['sources'].pop()
        self.assertIsNone(reuse_same_day(self.proof, self.now.date(), self.now))
