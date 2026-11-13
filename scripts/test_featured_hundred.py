"""KRX-100 migration, unlimited qualifying themes and legacy-feed isolation."""
import copy
import datetime as dt
import unittest
from unittest.mock import patch
from featured_stocks import KST, collect, enrich, validate, archive
from featured_scope import feed_prefix
from featured_watch import watch, index_matches
from publish_featured_stocks import publication_entries
from test_featured_strength import group
from test_featured_stocks import fixture


def snapshot():
    old=fixture();p=copy.deepcopy(old)
    p.update(schemaVersion=2,turnoverBasis='KRX',universeSize=100,
             asOf='2026-11-13T20:01:00+09:00',collectionStartedAt='2026-11-13T20:00:00+09:00',
             releaseAt='2026-11-13T20:10:00+09:00')
    p['sourceRecords']=[{'market':'KRX','sourceUrl':'https://stock.naver.com/api/domestic/',
                         'retrievedAt':p['collectionStartedAt']}]
    p['stocks']=[]
    for i in range(100):
        p['stocks'].append({'code':f'{i:06}','name':'test'+str(i),'turnoverRank':i+1,
                            'krxTradeAmount':10000-i,'tradeAmount':10000-i,
                            'changeRate':10 if i<15 else -1,'rateMarket':'KRX',
                            'quotes':{'KRX':{'observedAt':'2026-11-13T15:30:00+09:00',
                                             'sourceUrl':'https://stock.naver.com/api/domestic/detail/'+str(i)}}})
    for s in p['stocks']:
        s['closeVerification']={'basis':'KRX_REGULAR_CLOSE', 'tradeAmount':s['tradeAmount'], 'changeRate':s['changeRate'], **s['quotes']['KRX']}
    p['byTurnover']=[s['code'] for s in p['stocks']]
    p['byChangeRate']=p['byTurnover'][:]
    p['unclassified']=p['byTurnover'][:]
    return p


def staged(groups=None):
    if groups is None:groups=[group([f'{i:06}' for i in range(j,j+3)],'theme'+str(j)) for j in range(0,15,3)]
    return enrich(snapshot(),{'reviewedAt':'2026-11-13T20:05:00+09:00','themes':groups})


class HundredTests(unittest.TestCase):
    def test_five_qualifying_themes_are_all_published(self):
        p=staged()
        self.assertEqual(p['themeSelectionVersion'],3)
        self.assertEqual(len(p['themes']),5)
        self.assertIn('5위',p['reportMarkdown'])
        self.assertEqual(len(p['stocks']),100)

    def test_all_hundred_including_members_below_fifty_are_eligible(self):
        p=snapshot()
        for s in p['stocks'][70:73]:s['changeRate']=25;s['closeVerification']['changeRate']=25
        p['byChangeRate']=[s['code'] for s in sorted(p['stocks'],key=lambda s:(-s['changeRate'],-s['tradeAmount'],s['code']))]
        r=enrich(p,{'reviewedAt':'2026-11-13T20:05:00+09:00',
                    'themes':[group(['000070','000071','000072'])]})
        self.assertEqual(len(r['themes']),1)
        self.assertIn('000072',r['themes'][0]['stockCodes'])

    def test_truncated_or_duplicated_hundred_rejected(self):
        for count in [50,99,101]:
            p=staged();p['stocks']=(p['stocks']+[p['stocks'][0]])[:count]
            with self.assertRaisesRegex(ValueError,'100 unique'):validate(p)

    def test_cannot_zero_fill_nxt_or_mislabel_basis(self):
        for field,value in [('turnoverBasis','KRX_NXT'),('universeSize',50)]:
            p=staged();p[field]=value
            with self.assertRaises(ValueError):validate(p)
        p=staged();p['stocks'][0]['nxtTradeAmount']=0
        with self.assertRaisesRegex(ValueError,'zero-fill'):validate(p)

    def test_v1_cannot_replace_new_hundred_edition(self):
        p=staged();p['schemaVersion']=1
        with self.assertRaisesRegex(ValueError,'edition'):validate(p)

    def test_old_top_three_snapshot_is_not_retroactively_changed(self):
        from test_featured_strength import snapshot as old_snapshot,stage
        p=old_snapshot()
        for s in p['stocks'][:12]:s['changeRate']=12
        r=stage(p,[group([f'{i:06}' for i in range(j,j+3)],str(j)) for j in range(0,12,3)])
        self.assertEqual(len(r['themes']),3)
        self.assertEqual(r['themeSelectionVersion'],2)

    def test_new_publication_never_overwrites_legacy_paths(self):
        p=staged();entries,index=publication_entries(p,archive(p),['2026-11-09','2026-11-12','2026-11-13'])
        self.assertEqual(feed_prefix(p),'featured-stocks-v2')
        self.assertTrue(all(e['path'].startswith('featured-stocks-v2') for e in entries))
        self.assertEqual(index['schemaVersion'],2)
        self.assertTrue(index_matches(index,p))
        index['dates'][0]['path']='featured-stocks/2026-11-13.json'
        self.assertFalse(index_matches(index,p))

    def test_publisher_checks_all_three_v2_paths_and_report(self):
        import publish_featured_stocks as pub
        import base64
        p=staged();api_calls=[];reads=[]
        def api(method,path,body=None):
            api_calls.append((method,path,body))
            if path=='git/ref/heads/main':return {'object':{'sha':'old'}}
            if path=='git/commits/old':return {'tree':{'sha':'base'}}
            if path.startswith('git/trees/') :return {'tree':[]}
            if path=='git/trees':return {'sha':'tree'}
            if path=='git/commits':return {'sha':'new'}
            if path.startswith('contents/'):return {'content':base64.b64encode(p['reportMarkdown'].encode()).decode()}
            return {}
        def read(path,ref='main',missing=False):
            reads.append((path,ref))
            if ref=='old':return None,None
            if path=='featured-stocks-v2.json':return p,None
            if path.endswith('/index.json'):return publication_entries(p,archive(p),['2026-11-13'])[1],None
            return archive(p),None
        with patch.object(pub,'api',side_effect=api),patch.object(pub,'read_remote',side_effect=read):
            self.assertEqual(pub.publish(p),'new')
        self.assertFalse(any(path.startswith('featured-stocks/') or path=='featured-stocks.json' for path,ref in reads))
        self.assertTrue(any(path=='contents/featured-stocks-v2/latest.md?ref=new' for method,path,body in api_calls))

    def test_watch_confirms_v2_root_archive_index(self):
        p=staged();date='2026-11-13';release=dt.datetime.fromisoformat(p['releaseAt'])
        entries,index=publication_entries(p,archive(p),[date]);seen=[]
        def read(path,ref='main',missing=False):
            seen.append(path)
            if path=='featured-stocks-v2.json':return p,None
            if path=='featured-stocks-v2/'+date+'.json':return archive(p),None
            if path=='featured-stocks-v2/index.json':return index,None
            raise AssertionError(path)
        r=watch(release,lambda s:None,read=read,clock=lambda:release)
        self.assertTrue(r['published'])
        self.assertTrue(all(x.startswith('featured-stocks-v2') for x in seen))

    def test_collector_uses_full_krx_and_never_calls_nxt(self):
        calls=[]
        rows=[{'type':'ST','itemcode':f'{i:06}','itemname':'test','tradeAmount':str(20000-i),
               'prevChangeRate':'1.2','marketSum':'123000000','nowPrice':'100','upperLimitPrice':'100'} for i in range(1100)]
        def fetch(url):
            calls.append(url)
            self.assertNotIn('NXT',url)
            if '/market/stock/' in url:return rows
            code=url.split('/detail/')[1].split('/')[0]
            return {'itemcode':code,'tradeTime':'20261113153000','tradeAmount':str(20000-int(code)),'prevChangeRate':'1.2'}
        p=collect('2026-11-13T20:10:00+09:00',{'date':'2026-11-13','tradingDayVerified':True,
                  'calendarSourceUrl':'https://global.krx.co.kr/calendar'},fetch=fetch,
                  now=dt.datetime(2026,11,13,20,0,tzinfo=KST),full_nxt=True,
                  eligibility_fetch=lambda:self.fail('NXT must not be queried'))
        self.assertEqual(len(p['stocks']),100)
        self.assertEqual(len(calls),101)
        self.assertTrue(p['stocks'][0]['isUpperLimit'])
        self.assertNotIn('nxtTradeAmount',p['stocks'][0])
        enrich(p,{'reviewedAt':'2026-11-13T20:05:00+09:00','themes':[]})
        with self.assertRaisesRegex(ValueError,'partial top 100'):
            collect('2026-11-13T20:10:00+09:00',{'date':'2026-11-13','tradingDayVerified':True,
                    'calendarSourceUrl':'https://global.krx.co.kr/calendar'},fetch=lambda u:rows[:100],
                    now=dt.datetime(2026,11,13,20,0,tzinfo=KST))

    def test_majority_decliners_and_individual_events_still_excluded(self):
        p=snapshot();p['stocks'][1]['changeRate']=-10;p['stocks'][2]['changeRate']=-10
        for s in p['stocks']:s['closeVerification']['changeRate']=s['changeRate']
        p['byChangeRate']=[s['code'] for s in sorted(p['stocks'],key=lambda s:(-s['changeRate'],-s['tradeAmount'],s['code']))]
        r=enrich(p,{'reviewedAt':'2026-11-13T20:05:00+09:00','themes':[group(['000000','000001','000002'])]})
        self.assertFalse(r['themes'])
        self.assertEqual(r['themeAssessments'][0]['strength']['judgment'],'약세')
        self.assertFalse(staged([group(['000000','000001','000002'],kind='individual_event')])['themes'])

    def test_report_truncation_is_rejected(self):
        p=staged();p['themes']=p['themes'][:3]
        with self.assertRaisesRegex(ValueError,'mismatch'):validate(p)
