import copy
import datetime as dt
import unittest
from unittest.mock import Mock
import us_themes as u
import us_theme_worker as worker
from prepare_feed import validate


RELEASE = dt.datetime(2026, 11, 16, 6, 40, tzinfo=u.KST)
CHECKED = RELEASE-dt.timedelta(minutes=10)
OBSERVED = '2026-11-13T16:00:00-05:00'


def provider(url):
    if url == u.INDEX_URL:
        return {'isSuccess': True, 'result': [{'id': ident, 'localTradedAt': OBSERVED, 'marketStatus': 'CLOSE'} for ident in ('.DJI', '.IXIC')]}
    if 'stock/list?' in url:
        from urllib.parse import urlparse, parse_qs
        page = int(parse_qs(urlparse(url).query)['page'][0])
        rows = [{'id': 'S'+str(i)+'.O', 'stockEndType': 'stock', 'currencyType': 'USD', 'marketStatus': 'CLOSE',
                 'accumulatedTradingValue': 10000-i, 'fluctuationsRatio': str(1+i%5),
                 'currentPrice': 0.01, 'accumulatedTradingVolume': 999999999}
                for i in range((page-1)*50+1, page*50+1)]
        return {'isSuccess': True, 'result': {'page': page, 'marketStatus': 'CLOSE', 'stocks': rows}}
    code = url.split('/')[-2]
    ident = int(code[1:-2])
    return {'reutersCode': code, 'symbolCode': 'S'+str(ident), 'stockName': 'Fixture '+str(ident),
            'stockCodeClassificationType': 'ADR' if ident == 2 else 'ORD', 'isEtf': False,
            'stockExchangeType': {'name': 'NASDAQ'}, 'currencyType': {'name': 'USD'},
            'localTradedAt': OBSERVED, 'marketStatus': 'CLOSE', 'fluctuationsRatio': str(1+ident%5),
            'industryCodeType': {'industryGroupKor': 'Fixture industry'},
            'overMarketPriceInfo': {'fluctuationsRatio': '99', 'overMarketStatus': 'OPEN'}}


def snapshot():
    return u.collect_snapshot(RELEASE.isoformat(), get=provider, now=CHECKED)


def review(data):
    return {'sessionDate': data['sessionDate'], 'reviewedAt': CHECKED.isoformat(),
            'groups': [{'id': str(g), 'name': '검증용 테마 '+str(g),
                        'members': [{'id': s['id'], 'classificationSourceUrl': s['classificationSourceUrl']}
                                    for s in data['stocks'] if (s['rank']-1)%5 == g]}
                       for g in range(5)]}


def payload():
    coverage = {key: {'checkedAt': CHECKED.isoformat(), 'sourceUrls': ['https://example.com/test']}
                for key in ('foreign_market','foreign_policy','foreign_technology','domestic_disclosures','domestic_policy','domestic_market')}
    return {'schemaVersion': 2, 'releaseAt': RELEASE.isoformat(), 'asOf': CHECKED.isoformat(),
            'tradingDayVerified': True, 'calendarSourceUrl': 'https://example.com/calendar', 'items': [],
            'researchAudit': {'coverage': coverage, 'foreignCandidates': 0, 'domesticCandidates': 0,
                              'verifiedCandidates': 0, 'duplicateExcluded': 0}}


class USThemeTests(unittest.TestCase):
    def test_us_holiday_weekend_early_close_and_dst_calendar(self):
        self.assertEqual(str(u.previous_us_session(dt.datetime(2026,11,27,6,25,tzinfo=u.KST))), '2026-11-25')
        self.assertEqual(str(u.previous_us_session(dt.datetime(2026,11,16,6,25,tzinfo=u.KST))), '2026-11-13')
        self.assertEqual(str(u.previous_us_session(dt.datetime(2026,11,27,13,30,tzinfo=u.NY))), '2026-11-27')
        self.assertEqual(str(u.previous_us_session(dt.datetime(2026,7,7,6,25,tzinfo=u.KST))), '2026-07-06')
        with self.assertRaises(ValueError): u.previous_us_session(dt.datetime(2029,1,2,6,25,tzinfo=u.KST))

    def test_consistent_but_stale_quotes_do_not_count_as_last_session(self):
        data = snapshot()
        data['collectedAt'] = '2026-11-17T06:30:00+09:00'
        with self.assertRaisesRegex(ValueError, 'last completed'): u.validate_snapshot(data)

    def test_actual_dollar_turnover_and_regular_quote_used_not_volume_or_afterhours(self):
        data = snapshot()
        self.assertEqual(len(data['stocks']), 50)
        self.assertEqual(data['stocks'][0]['tradeAmountUsd'], 9999)
        self.assertEqual(data['stocks'][0]['changeRate'], 2)
        self.assertEqual(data['stocks'][1]['securityType'], 'ADR')

    def test_exclude_funds_and_preferred_then_fill_eligible_top_50(self):
        def fetch(url):
            obj = provider(url)
            if '/S1.O/basic' in url:
                obj.update(stockCodeClassificationType='ETF', isEtf=True)
            if '/S2.O/basic' in url:
                obj['stockCodeClassificationType'] = 'PREFERRED'
            return obj
        data = u.collect_snapshot(RELEASE.isoformat(), fetch, CHECKED)
        self.assertEqual(data['stocks'][0]['id'], 'S3.O')
        self.assertEqual(data['stocks'][-1]['id'], 'S52.O')
        self.assertEqual(len(data['excluded']), 2)

    def test_missing_trade_amount_is_not_estimated_from_price_times_volume(self):
        def fetch(url):
            obj = provider(url)
            if 'stock/list?' in url: del obj['result']['stocks'][0]['accumulatedTradingValue']
            return obj
        with self.assertRaises(ValueError): u.collect_snapshot(RELEASE.isoformat(), fetch, CHECKED)

    def test_wrong_session_or_unknown_security_type_is_not_silently_dropped(self):
        for field, value in [('localTradedAt', '2026-11-12T16:00:00-05:00'), ('stockCodeClassificationType', None)]:
            def fetch(url):
                obj = provider(url)
                if '/S1.O/basic' in url: obj[field] = value
                return obj
            with self.assertRaises(ValueError): u.collect_snapshot(RELEASE.isoformat(), fetch, CHECKED)

    def test_only_0640_collects_and_probe_cannot_be_published(self):
        fetch = Mock()
        with self.assertRaises(ValueError): u.collect_snapshot('2026-11-16T07:40:00+09:00', fetch, CHECKED)
        fetch.assert_not_called()
        data = u.collect_snapshot(RELEASE.isoformat(), provider, CHECKED, probe=True)
        with self.assertRaisesRegex(ValueError, 'probe'): u.attach(payload(), data, review(data))

    def test_maximum_three_weighted_themes_and_existing_apk_compatible_top_card(self):
        data = snapshot()
        report = u.build_report(data, review(data), RELEASE.isoformat(), CHECKED.isoformat())
        self.assertEqual(len(report['themes']), 3)
        self.assertEqual(report['themes'][0]['weightedChangeRate'], 5)
        composed = u.attach(payload(), data, review(data))
        validate(composed)
        self.assertEqual(composed['items'][0]['impactRank'], 1)
        self.assertEqual(composed['items'][0]['kind'], 'news')
        self.assertEqual(composed['items'][0]['role'], u.ROLE)

    def test_turnover_weighting_changes_result_and_all_members_are_in_denominator(self):
        data = snapshot()
        rev = review(data)
        rev['groups'] = [{'id': 'all', 'name': '전체 검증용', 'members': [m for g in rev['groups'] for m in g['members']]}]
        data['stocks'][0]['tradeAmountUsd'] = 1000000
        top = u.aggregate(data, rev, CHECKED)
        expected = sum(s['tradeAmountUsd']*s['changeRate'] for s in data['stocks'])/sum(s['tradeAmountUsd'] for s in data['stocks'])
        self.assertAlmostEqual(top[0]['weightedChangeRate'], expected, places=6)

    def test_duplicate_or_unassigned_member_blocks_strongest_theme_claim(self):
        data = snapshot()
        for duplicate in (False, True):
            rev = review(data)
            if duplicate: rev['groups'][0]['members'].append(rev['groups'][1]['members'][0])
            else: rev['groups'][0]['members'].pop()
            with self.assertRaises(ValueError): u.aggregate(data, rev, CHECKED)

    def test_missing_review_or_collection_failure_displays_unavailable_without_fake_rates(self):
        data = snapshot()
        for record in (data, {'releaseAt': RELEASE.isoformat(), 'state': 'collection_failed', 'checkedAt': CHECKED.isoformat()}):
            composed = u.attach(payload(), record)
            validate(composed)
            self.assertIn('미집계', composed['items'][0]['title'])
            self.assertNotIn('%', composed['items'][0]['summary'])

    def test_zero_positive_themes_does_not_invent_three_winners(self):
        data = snapshot()
        for row in data['stocks']: row['changeRate'] = -1
        self.assertEqual(u.aggregate(data, review(data), CHECKED), [])

    def test_other_editions_forbid_us_theme_block_and_0640_requires_it(self):
        with self.assertRaisesRegex(ValueError, 'requires'): validate(payload())
        data = snapshot()
        composed = u.attach(payload(), data, review(data))
        composed['releaseAt'] = '2026-11-16T07:40:00+09:00'
        composed['asOf'] = '2026-11-16T07:30:00+09:00'
        with self.assertRaisesRegex(ValueError, 'outside 06:40'): validate(composed)

    def test_tampered_ranking_summary_or_position_is_rejected(self):
        data = snapshot()
        for field in ('score', 'text', 'position'):
            composed = u.attach(payload(), data, review(data))
            if field == 'score': composed['usThemeReport']['themes'][0]['weightedChangeRate'] += 1
            elif field == 'text': composed['items'][0]['summary'] += 'invented'
            else: composed['items'].insert(0, {'id': 'bad'})
            with self.assertRaises(ValueError): validate(composed)

    def test_theme_reason_published_after_target_is_rejected_during_recovery(self):
        data = snapshot()
        rev = review(data)
        rev['reviewedAt'] = (RELEASE+dt.timedelta(minutes=5)).isoformat()
        rev['groups'][0]['reason'] = {'summary': '검증용 사실', 'sourceUrl': 'https://example.com/event',
            'publishedAt': (RELEASE+dt.timedelta(minutes=1)).isoformat(), 'causality': 'related_fact_only'}
        with self.assertRaises(ValueError):
            u.build_report(data, rev, RELEASE.isoformat(), (RELEASE+dt.timedelta(minutes=5)).isoformat())

    def test_real_failure_status_persists_without_becoming_public_news(self):
        saved = {}
        result = worker.run(RELEASE.isoformat(), 'fixture', collector=Mock(side_effect=TimeoutError('source timeout')),
                            persist=lambda p, v: saved.update({p: copy.deepcopy(v)}))
        self.assertEqual(result['state'], 'collection_failed')
        self.assertTrue(all(p.startswith('operations/us-theme-sources/') for p in saved))
        self.assertFalse(result['publishable'])


if __name__ == '__main__': unittest.main()
