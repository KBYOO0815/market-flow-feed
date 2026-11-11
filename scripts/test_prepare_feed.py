import copy
import datetime as dt
import unittest
from prepare_feed import KST, prepare, validate, check_release

class EditorialFreshnessTests(unittest.TestCase):
    def payload(self, hour=11, minute=30):
        release = dt.datetime(2026, 11, 11, hour, minute, tzinfo=KST)
        review = release - dt.timedelta(minutes=5)
        return {'schemaVersion':2,'tradingDayVerified':True,'calendarSourceUrl':'https://global.krx.co.kr/','asOf':review.isoformat(),'releaseAt':release.isoformat(),'items':[{
            'id':'test-only-event','title':'검증용 기업 공시','summary':'화면에 게시하지 않는 단위 검사 데이터.',
            'sourceName':'Test fixture','sourceUrl':'https://example.com/event','reviewSourceUrl':'https://example.com/update',
            'publishedAt':(review-dt.timedelta(days=1)).isoformat(),'reviewedAt':review.isoformat(),
            'validUntil':(release+dt.timedelta(minutes=30)).isoformat(),'reviewNote':'후속 공시를 확인한 검증용 설명.',
            'region':'domestic','category':'국내공시','impactRank':1,'relatedStocks':[],'kind':'news'}]}
    def test_all_four_slots(self):
        for hour, minute in [(7,30),(11,30),(15,30),(20,0)]:
            validate(self.payload(hour,minute))
    def test_early_scheduler_start_can_prepare_the_intended_slot(self):
        p=self.payload(15,30)
        p['asOf']='2026-11-11T15:15:00+09:00'
        p['items'][0]['reviewedAt']=p['asOf']
        p['items'][0]['publishedAt']='2026-11-10T12:00:00+09:00'
        validate(p)
    def test_old_opening_quote_is_rejected(self):
        p=self.payload();i=p['items'][0];i.update(kind='market_snapshot',summary='장 초반 약세',observedAt='2026-11-11T09:32:00+09:00')
        with self.assertRaisesRegex(ValueError,'observation is stale'):
            validate(p)
    def test_copy_without_current_review_is_rejected(self):
        p=self.payload();p['items'][0]['reviewedAt']='2026-11-11T07:20:00+09:00'
        with self.assertRaisesRegex(ValueError,'rechecked'):
            validate(p)
    def test_intraday_claim_cannot_hide_as_event_news(self):
        p=self.payload();p['items'][0]['summary']='장중 주가가 상승했다.'
        with self.assertRaisesRegex(ValueError,'market_snapshot'):
            validate(p)
    def test_prepublication_is_blocked(self):
        p=self.payload()
        with self.assertRaises(ValueError):
            prepare(p,dt.datetime(2026,11,11,11,29,tzinfo=KST))
    def test_stale_slot_is_blocked(self):
        p=self.payload()
        with self.assertRaises(ValueError):
            prepare(p,dt.datetime(2026,11,11,15,30,tzinfo=KST))
    def test_expired_quotes_dropped_without_inventing_replacements(self):
        p=self.payload();i=p['items'][0];i.update(kind='market_snapshot',observedAt='2026-11-11T11:25:00+09:00',validUntil='2026-11-11T11:40:00+09:00')
        self.assertEqual(prepare(p,dt.datetime(2026,11,11,11,41,tzinfo=KST))['items'],[])
    def test_old_factual_news_requires_fresh_review(self):
        self.assertEqual(len(prepare(self.payload(),dt.datetime(2026,11,11,11,30,tzinfo=KST))['items']),1)
    def test_forged_future_review_is_rejected(self):
        p=self.payload();p['items'][0]['reviewedAt']='2026-11-11T11:26:00+09:00'
        with self.assertRaises(ValueError):
            validate(p)

if __name__=='__main__':
    unittest.main()
