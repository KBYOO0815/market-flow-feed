import copy
import datetime as dt
import unittest
import urllib.error
from unittest.mock import Mock
import featured_stocks as f


NOW = dt.datetime(2026,11,13,9,30,tzinfo=f.KST)
RELEASE = '2026-11-13T09:40:00+09:00'
EVIDENCE = {'date':'2026-11-13','tradingDayVerified':True,'calendarSourceUrl':'https://example.com/calendar'}


def source(url):
    if 'tradeType=KRX' in url:
        return [{'itemcode':f'{i:06}', 'itemname':'test-only', 'type':'ST', 'prevChangeRate':'2.5',
                 'tradeAmount': str(100000-i)} for i in range(1100)]
    if 'tradeType=NXT' in url:
        rows = [{'itemcode':f'{i:06}','type':'ST','tradeAmount':str(10000-i)} for i in range(100)]
        rows[5],rows[6] = rows[6],rows[5]
        return rows
    code = url.split('/detail/')[1][:6]
    return {'itemcode':code,'tradeAmount':str(10000000 if code=='000149' and 'codeType=NXT' in url else 5000-int(code)),
            'tradeTime':'20261113093000'}


def official():
    return {'totalCnt':150,'records':150,'total':1,'setTime':'2026-11-13 09:10',
            'brdinfoTimeList':[{'isuSrdCd':'A'+f'{i:06}','aggDd':'20261113','nowDd':'20261113'} for i in range(150)]}


class FeaturedRecoveryTests(unittest.TestCase):
    def test_unsorted_truncated_list_uses_complete_official_universe_and_finds_omitted_winner(self):
        events = []
        snap = f.collect(RELEASE,EVIDENCE,source,NOW,official,trace=events.append)
        self.assertEqual(snap['byTurnover'][0], '000149')
        self.assertEqual(len(snap['stocks']),50)
        self.assertIn('nxt_order_inversion',[e['stage'] for e in events])
        complete = next(e for e in events if e['stage']=='nxt_full_scan_verified')
        self.assertEqual(complete['exactQuotes'],150)
        self.assertEqual(len(snap['sourceRecords']),153)  # two lists, 150 exact NXT, official proof.

    def test_even_sorted_fast_list_can_be_verified_with_server_full_scan(self):
        def get(url):
            obj=source(url)
            if 'tradeType=NXT' in url: obj.sort(key=lambda r:-int(r['tradeAmount']))
            return obj
        snap = f.collect(RELEASE,EVIDENCE,get,NOW,official,full_nxt=True)
        self.assertEqual(snap['byTurnover'][0],'000149')

    def test_official_eligible_404_remains_unknown_and_not_zero(self):
        def get(url):
            if '/000149/' in url and 'codeType=NXT' in url:
                raise urllib.error.HTTPError(url,404,'missing',{},None)
            return source(url)
        with self.assertRaisesRegex(ValueError,'404 is not zero'): f.collect(RELEASE,EVIDENCE,get,NOW,official)

    def test_stale_official_list_cannot_establish_complete_universe(self):
        bad=official();bad['setTime']='2026-11-12 09:10'
        with self.assertRaises(ValueError): f.collect(RELEASE,EVIDENCE,source,NOW,lambda:bad)

    def test_duplicate_ids_are_not_silently_overwritten(self):
        def get(url):
            obj=source(url)
            if 'tradeType=NXT' in url: obj.append(copy.deepcopy(obj[0]))
            return obj
        with self.assertRaisesRegex(ValueError,'duplicate ranking'): f.collect(RELEASE,EVIDENCE,get,NOW,official)

    def test_probe_can_test_full_collection_outside_release_window_but_never_stage(self):
        later=NOW+dt.timedelta(hours=1)
        def current_source(url):
            obj=source(url)
            if isinstance(obj,dict):obj['tradeTime']='20261113103000'
            return obj
        snap=f.collect(RELEASE,EVIDENCE,current_source,later,lambda:{**official(),'setTime':'2026-11-13 10:10'},probe=True)
        self.assertTrue(snap['probeOnly'])
        with self.assertRaisesRegex(ValueError,'not publishable'): f.enrich(snap,{'reviewedAt':later.isoformat(),'themes':[]})
        with self.assertRaisesRegex(ValueError,'outside original'): f.collect(RELEASE,EVIDENCE,source,later,official)


if __name__=='__main__': unittest.main()
