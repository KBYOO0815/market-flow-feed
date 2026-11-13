"""Regression cases exercise policy outcomes, publication and v1 compatibility."""
import copy
import unittest
from featured_stocks import enrich, validate, archive
from featured_strength import analyze, NO_REASON
from publish_featured_stocks import publication_entries
from test_featured_stocks import fixture


def snapshot():
    p = fixture()
    def shift(v):
        if isinstance(v, str): return v.replace('2026-11-12T09:', '2026-11-13T15:')
        if isinstance(v, list): return [shift(x) for x in v]
        if isinstance(v, dict): return {k:shift(x) for k,x in v.items()}
        return v
    p = shift(p)
    for s in p['stocks']: s['changeRate'] = -1
    return p


def group(codes, name='검증 테마', kind='industry', event='ordinary', cause=None):
    return {'id': name, 'name': name, 'stockCodes': codes,
            'groupingBasis': {'kind':kind,'sourceUrl':'https://example.com/ir','fact':'test grouping evidence'},
            'membershipEvidence': [{'code':c,'sourceUrl':'https://example.com/ir',
                                    'fact':'test same industry evidence','eventType':event,
                                    'valueChainRole':'unknown'} for c in codes], 'reason':cause}


def stage(p, groups):
    p['byChangeRate'] = [s['code'] for s in sorted(p['stocks'],key=lambda s:(-s['changeRate'],-s['integratedTradeAmount'],s['code']))]
    return enrich(p, {'reviewedAt':'2026-11-13T15:35:00+09:00','themes':groups})


class StrengthTests(unittest.TestCase):
    def test_broad_theme_beats_one_large_gainer(self):
        p=snapshot()
        p['stocks'][0]['changeRate']=29
        for s in p['stocks'][1:5]: s['changeRate']=11
        result=stage(p,[group(['000000'],'single'),group([f'{i:06}' for i in range(1,5)],'broad')])
        self.assertEqual([t['id'] for t in result['themes']],['broad'])
        self.assertIn('개별 강세',[t['strength']['judgment'] for t in result['themeAssessments']])

    def test_most_members_falling_cannot_lead(self):
        p=snapshot(); p['stocks'][0]['changeRate']=29
        r=stage(p,[group([f'{i:06}' for i in range(5)])])
        self.assertEqual(r['themes'],[])
        self.assertEqual(r['themeAssessments'][0]['strength']['judgment'],'약세')

    def test_single_leader_plus_laggards_not_cherry_picked(self):
        p=snapshot()
        for i,rate in enumerate([20,0,0,-1]): p['stocks'][i]['changeRate']=rate
        r=stage(p,[group([f'{i:06}' for i in range(4)])])
        self.assertFalse(r['themes'])
        self.assertEqual(r['themeAssessments'][0]['strength']['risingCount'],1)

    def test_small_money_gainers_are_excluded(self):
        p=snapshot()
        for s in p['stocks'][:3]:
            s['changeRate']=29; s['krxTradeAmount']=0; s['nxtTradeAmount']=1;s['integratedTradeAmount']=1
        p['stocks'].sort(key=lambda s:(-s['integratedTradeAmount'],s['code']))
        for i,s in enumerate(p['stocks'],1):s['turnoverRank']=i
        p['byTurnover']=[s['code'] for s in p['stocks']]
        r=stage(p,[group(['000000','000001','000002'])])
        self.assertFalse(r['themes'])
        self.assertIn('입력 전체 대비 상승 종목 거래대금 1% 미만',r['themeAssessments'][0]['strength']['exclusionReasons'])

    def test_special_events_not_industry_leader(self):
        for event in ['preferred','ipo','tender_offer','control_dispute','other_event','unknown']:
            p=snapshot()
            for s in p['stocks'][:3]:s['changeRate']=20
            self.assertFalse(stage(p,[group(['000000','000001','000002'],event=event)])['themes'])

    def test_unrelated_or_uncertain_groups_not_leader(self):
        for kind in ['individual_event','uncertain']:
            p=snapshot()
            for s in p['stocks'][:3]:s['changeRate']=20
            self.assertFalse(stage(p,[group(['000000','000001','000002'],kind=kind)])['themes'])

    def test_output_max_three_and_no_fabricated_cause(self):
        p=snapshot()
        for s in p['stocks'][:12]:s['changeRate']=12
        r=stage(p,[group([f'{i:06}' for i in range(n,n+3)],str(n)) for n in range(0,12,3)])
        self.assertEqual(len(r['themes']),3)
        self.assertEqual(len(r['themeAssessments']),4)
        self.assertEqual(r['reportMarkdown'].count(NO_REASON),3)
        self.assertNotIn('4위',r['reportMarkdown'])
        self.assertEqual(len(set(r['unclassified'])|{c for t in r['themes'] for c in t['stockCodes']}),50)

    def test_rank_can_reverse_weighted_mean(self):
        p=snapshot()
        for s in p['stocks'][:5]:s['changeRate']=11
        for s in p['stocks'][30:33]:s['changeRate']=20
        r=stage(p,[group([f'{i:06}' for i in range(5)],'broad_money'),group([f'{i:06}' for i in range(30,33)],'higher_return')])
        self.assertEqual(r['themes'][0]['id'],'broad_money')
        self.assertLess(r['themes'][0]['weightedChangeRate'],r['themes'][1]['weightedChangeRate'])

    def test_outside_input_and_cross_theme_duplicate_rejected(self):
        for groups in [[group(['999999'])],[group(['000000']),group(['000000'],'other')]]:
            with self.assertRaises(ValueError):stage(snapshot(),groups)

    def test_tampered_score_report_and_selection_rejected(self):
        p=snapshot()
        for s in p['stocks'][:3]:s['changeRate']=12
        r=stage(p,[group(['000000','000001','000002'])])
        for field in ['score','report','selection','membership']:
            bad=copy.deepcopy(r)
            if field=='score':bad['themeAssessments'][0]['strength']['score']=100
            if field=='report':bad['reportMarkdown']='invented'
            if field=='selection':bad['themes']=[]
            if field=='membership':bad['themeAssessments'][0]['stockCodes'].append('999999')
            with self.assertRaises((ValueError,KeyError)):validate(bad)

    def test_fresh_edition_cannot_use_legacy_policy(self):
        p=snapshot();p['reviewedAt']='2026-11-13T15:35:00+09:00'
        with self.assertRaisesRegex(ValueError,'version 2'):validate(p)

    def test_missing_evidence_fails(self):
        g=group(['000000']);del g['membershipEvidence'][0]['eventType']
        with self.assertRaisesRegex(ValueError,'eventType'):stage(snapshot(),[g])

    def test_company_news_cannot_be_expanded_to_industry(self):
        reason={'summary':'company deal','sourceUrl':'https://example.com/news',
                'publishedAt':'2026-11-13T15:00:00+09:00','checkedAt':'2026-11-13T15:35:00+09:00',
                'causality':'source_attributed','scope':'company'}
        with self.assertRaisesRegex(ValueError,'company catalyst'):stage(snapshot(),[group(['000000'],cause=reason)])

    def test_related_fact_explicitly_not_cause_and_old_news_rejected(self):
        p=snapshot()
        for s in p['stocks'][:3]:s['changeRate']=12
        reason={'summary':'related fact','sourceUrl':'https://example.com/news',
                'publishedAt':'2026-11-13T15:00:00+09:00','checkedAt':'2026-11-13T15:35:00+09:00',
                'causality':'related_fact_only','scope':'industry'}
        g=group(['000000','000001','000002'],cause=reason)
        r=stage(p,[g]);self.assertIn('상승 인과 확인 부족',r['reportMarkdown'])
        g['reason']['publishedAt']='2026-11-12T15:00:00+09:00'
        with self.assertRaisesRegex(ValueError,'publication'):stage(p,[g])

    def test_large_small_spread_requires_observed_caps_and_roles(self):
        p=snapshot()
        for s in p['stocks'][:3]:s['changeRate']=12
        g=group(['000000','000001','000002'])
        self.assertFalse(stage(p,[g])['themes'][0]['strength']['largeSmallSpreadVerified'])
        p['stocks'][0]['marketCapKrw']=20_000_000_000_000
        p['stocks'][1]['marketCapKrw']=1_000_000_000_000
        g['membershipEvidence'][0]['valueChainRole']='representative'
        g['membershipEvidence'][1]['valueChainRole']='equipment'
        self.assertTrue(stage(p,[g])['themes'][0]['strength']['largeSmallSpreadVerified'])

    def test_report_in_same_atomic_tree_and_empty_result(self):
        r=stage(snapshot(),[])
        self.assertIn('강한 테마 없음',r['reportMarkdown'])
        entries,_=publication_entries(r,archive(r),['2026-11-13'])
        report=next(e for e in entries if e['path']=='featured-stocks/latest.md')
        self.assertEqual(report['content'],r['reportMarkdown'])


if __name__=='__main__':unittest.main()
