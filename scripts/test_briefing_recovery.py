import datetime as dt
import json
import unittest
from unittest.mock import patch
from briefing_intent import validate_intent
from briefing_schedule import resolve
from prepare_feed import KST
from trading_day_evidence import KIND_QUOTE,NAVER_QUOTE,evidence,corroborated


class BriefingRecovery(unittest.TestCase):
    def setUp(self):self.now=dt.datetime(2026,11,13,16,0,tzinfo=KST);self.date=self.now.date()
    def request(self,mode='prepare'):return {'requestId':'edition-1550','releaseAt':'2026-11-13T15:50:00+09:00','mode':mode}
    def test_late_retry_uses_original_edition(self):
        release,mode=validate_intent(self.request(),self.now)
        self.assertEqual(release.hour,15);self.assertEqual(release.minute,50)
        self.assertEqual(mode,'prepare')
    def test_expired_1550_cannot_be_backfilled_at_1650(self):
        with self.assertRaisesRegex(ValueError,'expired'):
            validate_intent(self.request(),self.now.replace(hour=16,minute=50))
    def test_preparation_does_not_start_too_early(self):
        with self.assertRaises(ValueError):validate_intent(self.request(),self.now.replace(hour=15,minute=29))
    def test_diagnostic_explicitly_allowed_after_deadline(self):
        _,mode=validate_intent(self.request('diagnostic'),self.now.replace(hour=16,minute=50))
        self.assertEqual(mode,'diagnostic')
    def test_diagnostics_cannot_change_date(self):
        with self.assertRaises(ValueError):validate_intent(self.request('diagnostic'),self.now+dt.timedelta(days=1))
    def test_cron_anchor_keeps_1450_after_runner_starts_past_1550(self):
        created=self.now.replace(hour=14,minute=51)
        self.assertEqual(resolve(created,'50 2,5,6,9 * * 1-5').strftime('%H:%M'),'14:50')
        self.assertEqual(resolve(self.now,'50 2,5,6,9 * * 1-5').strftime('%H:%M'),'15:50')
    def body(self,date='2026-11-13',volume=100,amount=1000):
        return '<table summary="일자, 가격(원), 등락, 등락율, 거래량(주), 거래대금(원)"><tr><td>'+date+' 15:30:10</td><td>200</td><td>1</td><td>1%</td><td>'+str(volume)+'</td><td>'+str(amount)+'</td></tr></table>'
    def quote(self,time='20261113153000',volume='100',amount='1000'):
        return json.dumps({'itemcode':'005930','tradeTime':time,'tradeVolume':volume,'tradeAmount':amount})
    def test_actual_official_trade_plus_independent_quote_certifies_day(self):
        a=evidence(KIND_QUOTE,self.body(),self.date,self.now)
        b=evidence(NAVER_QUOTE,self.quote(),self.date,self.now)
        r=corroborated({'domestic_market':[{'marketTradeEvidence':a},{'marketTradeEvidence':b}]})
        self.assertTrue(r['verified']);self.assertEqual(r['calendarSourceUrl'],KIND_QUOTE)
    def test_http_success_header_date_or_only_one_source_is_insufficient(self):
        self.assertIsNone(evidence(KIND_QUOTE,'2026-11-13 15:30:10',self.date,self.now))
        a=evidence(KIND_QUOTE,self.body(),self.date,self.now)
        self.assertFalse(corroborated({'market':[{'marketTradeEvidence':a}]})['verified'])
    def test_stale_or_zero_trade_is_not_a_trading_day_certificate(self):
        for body in [self.body(date='2026-11-12'),self.body(volume=0),self.body(amount=0)]:
            self.assertIsNone(evidence(KIND_QUOTE,body,self.date,self.now))
        self.assertIsNone(evidence(NAVER_QUOTE,self.quote('20261112153000'),self.date,self.now))
    def test_future_or_premarket_quote_is_not_actual_regular_trade(self):
        self.assertIsNone(evidence(NAVER_QUOTE,self.quote('20261113153000'),self.date,self.now.replace(hour=15,minute=0)))
        self.assertIsNone(evidence(NAVER_QUOTE,self.quote('20261113084000'),self.date,self.now))

    def test_krx_after_hours_quote_can_corroborate_same_day_official_trade(self):
        official=evidence(KIND_QUOTE,self.body(),self.date,self.now.replace(hour=17))
        independent=evidence(NAVER_QUOTE,self.quote('20261113164000'),self.date,self.now.replace(hour=17))
        self.assertTrue(corroborated({'market':[{'marketTradeEvidence':official},{'marketTradeEvidence':independent}]})['verified'])

    def test_new_evidence_namespaces_can_be_saved_but_public_feed_cannot(self):
        import operation_store as store
        from unittest.mock import mock_open
        calls=[]
        def api(method,path,body=None):
            calls.append((method,path,body))
            if path=='git/ref/heads/main':return {'object':{'sha':'head'}}
            if path=='git/commits/head':return {'tree':{'sha':'base'}}
            return {'sha':'new'}
        with patch.object(store,'api',side_effect=api),patch.object(store.os,'makedirs'),patch('builtins.open',mock_open()):
            for ns in ['briefing-intents','briefing-diagnostics']:
                store.save('operations/'+ns+'/request-1550.json',{'published':False})
            for path in ['morning-briefing.json','operations/briefing-intents/../../morning-briefing.json']:
                with self.assertRaises(ValueError):store.save(path,{})
        self.assertEqual(sum(method=='PATCH' for method,path,body in calls),2)
