import copy
import datetime as dt
import unittest
from market_briefing import merge

TODAY = dt.date(2026, 11, 16)

def base_session(slot='06:40'):
    return {
        'slot': slot,
        'asOf': f'2026-11-16T{slot}:11+09:00',
        'usThemes': [],
        'foreignNews': [],
        'domesticNews': [],
        'researchStatus': 'complete',
        'usThemeStatus': 'insufficient_data' if slot == '06:40' else 'not_applicable',
    }

def draft(slot='06:40'):
    return {'date': str(TODAY), 'isKrxTradingDay': True, 'session': base_session(slot)}

def empty():
    return {'schemaVersion': 1, 'updatedAt': '2026-11-15T19:40:00+09:00', 'days': []}

def close_session():
    s = base_session('15:40')
    s['marketClose'] = {
        'summary': '코스피 강세, 코스닥 약세 마감',
        'kospi': {'close': 2500.12, 'changePct': 1.10},
        'kosdaq': {'close': 820.34, 'changePct': -0.20},
        'leadingThemes': ['반도체'],
        'weakThemes': ['바이오'],
        'sources': [{'name': 'KRX', 'url': 'https://example.org/krx'}],
    }
    return s

class MarketBriefingTest(unittest.TestCase):
    def test_replace_not_append(self):
        d = draft()
        one = merge(empty(), d, TODAY)
        two = merge(one, d, TODAY)
        self.assertEqual(len(two['days'][0]['sessions']), 1)

    def test_minimal_status_does_not_require_audit(self):
        d = draft()
        d['session']['researchStatus'] = 'partial'
        result = merge(empty(), d, TODAY)
        self.assertEqual(result['days'][0]['sessions'][0]['researchStatus'], 'partial')

    def test_verified_no_theme_does_not_require_top50_evidence(self):
        d = draft()
        d['session']['usThemeStatus'] = 'verified_no_theme'
        result = merge(empty(), d, TODAY)
        self.assertEqual(result['days'][0]['sessions'][0]['usThemeStatus'], 'verified_no_theme')

    def test_fifo_calendar_days(self):
        current = empty()
        current['days'] = [{'date': '2026-11-12', 'isKrxTradingDay': True, 'displaySlots': [], 'sessions': []}]
        self.assertEqual([d['date'] for d in merge(current, draft(), TODAY)['days']], ['2026-11-16'])

    def test_legacy_research_state_is_removed(self):
        current = empty()
        current['researchState'] = {'domesticNews': {'pendingWindows': [{}]}}
        result = merge(current, draft(), TODAY)
        self.assertNotIn('researchState', result)

    def test_closed_day_intraday_slot_rejected(self):
        d = draft('08:40')
        d['isKrxTradingDay'] = False
        with self.assertRaises(ValueError):
            merge(empty(), d, TODAY)

    def test_current_day_display_slots_follow_server_calendar(self):
        trading = merge(empty(), draft('06:40'), TODAY)
        self.assertEqual(trading['days'][0]['displaySlots'][0], '06:40')
        self.assertEqual(trading['days'][0]['displaySlots'][-1], '22:40')
        self.assertEqual(len(trading['days'][0]['displaySlots']), 15)

        holiday = draft('06:40')
        holiday['isKrxTradingDay'] = False
        closed = merge(empty(), holiday, TODAY)
        self.assertEqual(closed['days'][0]['displaySlots'], ['06:40', '22:40'])

    def test_closed_day_2240_accepted(self):
        d = draft('22:40')
        d['isKrxTradingDay'] = False
        result = merge(empty(), d, TODAY)
        self.assertEqual(result['days'][0]['sessions'][0]['slot'], '22:40')

    def test_closed_day_1940_rejected(self):
        d = draft('19:40')
        d['isKrxTradingDay'] = False
        with self.assertRaises(ValueError):
            merge(empty(), d, TODAY)

    def test_closed_day_market_close_rejected(self):
        d = {'date': str(TODAY), 'isKrxTradingDay': False, 'session': close_session()}
        with self.assertRaises(ValueError):
            merge(empty(), d, TODAY)

    def test_stale_replace_rejected(self):
        d = draft()
        current = merge(empty(), d, TODAY)
        d['session']['asOf'] = '2026-11-16T06:39:00+09:00'
        with self.assertRaises(ValueError):
            merge(current, d, TODAY)

    def test_cross_slot_fact_metadata_is_not_a_contract_constraint(self):
        d = draft()
        n = {
            'id': 'first', 'title': 'x', 'summary': 'x', 'sourceName': 'x', 'category': 'x',
            'region': 'foreign', 'impactRank': 1, 'relatedStocks': [],
            'sourceUrl': 'https://example.org', 'publishedAt': '2026-11-16T06:00:00+09:00',
            'eventKey': 'event', 'facts': [{'factKey': 'stable-fact'}],
        }
        d['session']['foreignNews'] = [n]
        current = merge(empty(), d, TODAY)
        later = draft('08:40')
        later['session']['foreignNews'] = [{**copy.deepcopy(n), 'id': 'renamed', 'impactRank': 1}]
        result = merge(current, later, TODAY)
        self.assertEqual(len(result['days'][0]['sessions']), 2)

    def test_future_news_rejected(self):
        d = draft()
        d['session']['foreignNews'] = [{
            'id': 'x', 'title': 'x', 'summary': 'x', 'sourceName': 'x', 'category': 'x',
            'region': 'foreign', 'impactRank': 1, 'relatedStocks': [],
            'sourceUrl': 'https://example.org', 'publishedAt': '2026-11-16T07:00:00+09:00',
        }]
        with self.assertRaises(ValueError):
            merge(empty(), d, TODAY)

    def test_1540_market_close_accepted(self):
        d = {'date': str(TODAY), 'isKrxTradingDay': True, 'session': close_session()}
        result = merge(empty(), d, TODAY)
        close = result['days'][0]['sessions'][0]['marketClose']
        self.assertEqual(close['kospi']['close'], 2500.12)

    def test_1540_general_news_accepted_without_market_close(self):
        d = draft('15:40')
        result = merge(empty(), d, TODAY)
        self.assertEqual(result['days'][0]['sessions'][0]['slot'], '15:40')
        self.assertIsNone(result['days'][0]['sessions'][0].get('marketClose'))

    def test_all_current_news_slots_accepted_on_trading_day(self):
        slots = ('06:40','07:40','08:40','09:40','10:40','11:40','12:40','13:40',
                 '14:40','15:40','16:40','17:40','18:40','19:40','22:40')
        current = empty()
        for slot in slots:
            current = merge(current, draft(slot), TODAY)
        self.assertEqual([x['slot'] for x in current['days'][0]['sessions']], list(slots))

    def test_market_close_rejected_outside_1540(self):
        d = draft('12:40')
        d['session']['marketClose'] = close_session()['marketClose']
        with self.assertRaises(ValueError):
            merge(empty(), d, TODAY)

if __name__ == '__main__':
    unittest.main()
