import copy
import datetime as dt
import unittest
from market_briefing import merge,validate,validate_session

TODAY=dt.date(2026,11,16)
def draft():
    start='2026-11-15T19:40:00+09:00';end='2026-11-16T06:42:00+09:00'
    domains={k:{'status':'partial','windowStartExclusive':start,'windowEndInclusive':end,'completedThrough':start,'pendingWindows':[{'startExclusive':start,'endInclusive':end}]} for k in ['foreignNews','domesticNews','usThemes']}
    return {'date':str(TODAY),'isKrxTradingDay':True,'session':{'slot':'06:40','asOf':end,'usThemes':[],'foreignNews':[],'domesticNews':[],'researchStatus':'partial','usThemeStatus':'insufficient_data','researchAudit':{'domains':domains}}}
def empty(): return {'schemaVersion':1,'updatedAt':'2026-11-15T19:40:00+09:00','days':[]}
class MarketBriefingTest(unittest.TestCase):
    def test_replace_not_append(self):
        d=draft();one=merge(empty(),d,TODAY);two=merge(one,d,TODAY)
        self.assertEqual(len(two['days'][0]['sessions']),1)
    def test_partial_not_complete(self):
        d=draft();d['session']['researchStatus']='complete'
        with self.assertRaises(ValueError):merge(empty(),d,TODAY)
    def test_no_theme_requires_full_evidence(self):
        d=draft();d['session']['usThemeStatus']='verified_no_theme'
        with self.assertRaises(ValueError):merge(empty(),d,TODAY)
    def test_fifo_calendar_days(self):
        current=empty();current['days']=[{'date':'2026-11-12','isKrxTradingDay':True,'sessions':[]}]
        self.assertEqual([d['date'] for d in merge(current,draft(),TODAY)['days']],['2026-11-16'])
    def test_pending_window_cannot_disappear(self):
        current=empty();current['researchState']={'domesticNews':{'completedThrough':'2026-11-15T19:40:00+09:00','pendingWindows':[{'startExclusive':'2026-11-15T19:40:00+09:00','endInclusive':'2026-11-16T06:42:00+09:00'}]}}
        d=draft();d['researchState']={'domesticNews':{'completedThrough':'2026-11-15T19:40:00+09:00','pendingWindows':[]}}
        with self.assertRaises(ValueError):merge(current,d,TODAY)
    def test_closed_day_slot_rejected(self):
        d=draft();d['isKrxTradingDay']=False;d['session']['slot']='08:40'
        with self.assertRaises(ValueError):merge(empty(),d,TODAY)
    def test_stale_replace_rejected(self):
        d=draft();current=merge(empty(),d,TODAY);d['session']['asOf']='2026-11-16T06:41:00+09:00'
        with self.assertRaises(ValueError):merge(current,d,TODAY)
    def test_future_news_rejected(self):
        d=draft();d['session']['foreignNews']=[{'id':'x','title':'x','summary':'x','sourceName':'x','category':'x','region':'foreign','impactRank':1,'relatedStocks':[],'sourceUrl':'https://example.org','publishedAt':'2026-11-16T07:00:00+09:00'}]
        with self.assertRaises(ValueError):merge(empty(),d,TODAY)
if __name__=='__main__': unittest.main()
