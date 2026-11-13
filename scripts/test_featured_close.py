import copy
import datetime as dt
import os
import unittest
from unittest.mock import Mock, patch
import featured_watch as watcher
from featured_krx import collect_krx
from featured_stocks import KST, validate
from test_featured_hundred import staged

class CloseSourceRegression(unittest.TestCase):
    def collect(self, observation='20261113153030', detail_amount=None, detail_rate='1.2'):
        rows=[{'type':'ST','itemcode':f'{i:06}','itemname':'test',
               'tradeAmount':str(20000-i),'prevChangeRate':'1.2'} for i in range(1100)]
        def fetch(url):
            if '/market/stock/' in url:return rows
            code=url.split('/detail/')[1].split('/')[0]
            return {'itemcode':code,'tradeTime':observation,
                    'tradeAmount':str(20000-int(code)) if detail_amount is None else detail_amount,
                    'prevChangeRate':detail_rate}
        return collect_krx('2026-11-13T20:10:00+09:00',
                          {'date':'2026-11-13','tradingDayVerified':True,'calendarSourceUrl':'https://kind.krx.co.kr/'},
                          fetch,now=dt.datetime(2026,11,13,20,0,tzinfo=KST))
    def test_after_hours_print_is_not_regular_close(self):
        for at in ['20261113195622','20261113160000','20261113153100']:
            with self.subTest(at=at), self.assertRaisesRegex(ValueError,'regular-session close'):
                self.collect(at)
    def test_close_list_and_detail_rates_and_amounts_must_match(self):
        for args in [{'detail_amount':'1'},{'detail_rate':'0'}]:
            with self.subTest(args=args), self.assertRaisesRegex(ValueError,'amount or rate mismatch'):
                self.collect(**args)
    def test_close_keeps_actual_observation_and_raw_value_comparison(self):
        p=self.collect()
        self.assertEqual(p['stocks'][0]['quotes']['KRX']['observedAt'],'2026-11-13T15:30:30+09:00')
        self.assertEqual(p['stocks'][0]['closeVerification']['tradeAmount'],20000)
    def test_staging_rejects_after_hours_and_forged_close_values(self):
        for kind in ['after_hours','amount','missing']:
            p=staged()
            if kind=='after_hours':p['stocks'][0]['quotes']['KRX']['observedAt']='2026-11-13T19:56:22+09:00'
            elif kind=='amount':p['stocks'][0]['closeVerification']['tradeAmount']+=1
            else:p['stocks'][0].pop('closeVerification')
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'close'):
                validate(p)

class CollectionHandoff(unittest.TestCase):
    def test_successful_collection_starts_watcher_for_pinned_original_request(self):
        request={'mode':'collect','releaseAt':'2026-11-13T20:10:00+09:00'}
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'KBYOO0815/market-flow-feed','COLLECTION_HEAD_SHA':'collection-commit','GITHUB_RUN_ID':'run','GITHUB_RUN_ATTEMPT':'1','EVENT_SCHEDULE':''}),patch.object(watcher,'read_remote',return_value=(request,'sha')) as read,patch.object(watcher,'watch',return_value={'state':'publication_missed'}) as watch:
            watcher.main()
        read.assert_called_once_with('requests/featured-collection.json','collection-commit')
        self.assertEqual(watch.call_args.args[0].isoformat(),request['releaseAt'])
    def test_probe_completion_does_not_start_publication(self):
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'KBYOO0815/market-flow-feed','COLLECTION_HEAD_SHA':'probe-commit'}),patch.object(watcher,'read_remote',return_value=({'mode':'collect_probe'},'sha')),patch.object(watcher,'watch') as watch:
            watcher.main()
        watch.assert_not_called()
