"""Synthetic contract tests; never used as production market data."""
import copy
import datetime as dt
import unittest
from featured_v3 import *
from publish_featured_v3 import merge


def fixture(slot='13:40',date='2026-11-16'):
    release=date+'T'+slot+':00+09:00';observed=date+'T'+slot+':01+09:00';asof=stamp(observed)+dt.timedelta(seconds=1)
    master=[];krx=[];nxt=[]
    for i in range(120):
        code=str(i).zfill(6)
        master.append({'code':code,'name':'TEST '+code,'market':'KOSPI','securityType':'PREFERRED' if i==1 else 'COMMON','classificationVerified':True,'classificationSourceUrl':'https://example.org/master'})
        q={'code':code,'market':'KRX','tradeDate':date,'turnoverScope':'KRX_ONLY','sourceUrl':'https://example.org/krx','retrievedAt':asof.isoformat(),'observedAt':observed,'session':'REGULAR_CLOSE' if slot=='20:10' else 'REGULAR_MARKET','closeConfirmed':slot=='20:10','turnover':10000-i*10,'price':104 if i%3==0 else 103.99,'previousRegularClose':100,'priceSourceUrl':'https://example.org/price'}
        krx.append(q)
        nxt.append({**q,'market':'NXT','turnoverScope':'NXT_ONLY','sourceUrl':'https://example.org/nxt','session':'NXT_FINAL' if slot=='20:10' else 'NXT_CUMULATIVE','turnover':10000 if i==110 else 50})
    coverage={'securityMasterComplete':True,'krxComplete':True,'nxtComplete':True,'nxtEligibleCodes':[s['code'] for s in master],'sourceUrl':'https://example.org/coverage','date':date}
    stocks,proof=rank_universe(master,krx,nxt,coverage,date,asof,slot)
    snapshot={'schemaVersion':3,'date':date,'slot':slot,'releaseAt':release,'asOf':asof.isoformat(),'collectionStartedAt':observed,'turnoverBasis':'KRX_NXT','universeSize':100,'amountUnit':'KRW','rateBasis':'KRX_PREVIOUS_CLOSE','stocks':stocks,'rankingProof':proof,'tradingDayEvidence':{'date':date,'verified':True,'isTradingDay':True,'sourceUrl':'https://example.org/calendar','checkedAt':observed,'facts':['TEST ONLY']}}
    return enrich(snapshot,{'reviewedAt':asof.isoformat(),'themes':[]})


class Contract(unittest.TestCase):
    def test_five_slots(self):
        self.assertEqual(SLOTS,('09:40','11:40','13:40','15:40','20:10'))
        for slot in SLOTS:self.assertEqual(validate(fixture(slot))['slot'],slot)
    def test_combined_challenger(self):
        p=fixture();self.assertEqual(p['stocks'][0]['code'],'000110');self.assertEqual(p['stocks'][0]['integratedTradeAmount'],18900)
    def test_all_four_percent(self):
        p=fixture();self.assertEqual(p['selectedStockCodes'],[s['code'] for s in p['stocks'] if s['changeRate']>=4]);self.assertTrue(any(s['securityType']=='PREFERRED' for s in p['stocks']))
    def test_bad_sum(self):
        p=fixture();p['stocks'][0]['nxtTradeAmount']+=1
        with self.assertRaises(ValueError):validate(p)
    def test_missing_nxt(self):
        p=fixture();p['rankingProof']['allMarketRows'][0]['quotes'].pop('NXT')
        with self.assertRaisesRegex(ValueError,'NXT eligible'):validate(p)
    def test_incomplete_coverage(self):
        p=fixture();p['rankingProof']['krxComplete']=False
        with self.assertRaisesRegex(ValueError,'complete market'):validate(p)
    def test_nontrading(self):
        p=fixture();p['tradingDayEvidence']['isTradingDay']=False
        with self.assertRaisesRegex(ValueError,'KRX closed'):validate(p)
    def test_exclusions(self):
        for security in ['ETF','ETN','SPAC','REIT','FUND','BOND','WARRANT']:
            self.assertFalse(eligible({'securityType':security,'market':'KOSPI','classificationVerified':True,'classificationSourceUrl':'https://example.org'}))
        with self.assertRaises(ValueError):eligible({'code':'000001'})
    def test_no_missing_or_duplicate(self):
        p=fixture();p['individualStocks'].pop()
        with self.assertRaisesRegex(ValueError,'incomplete'):validate(p)
        p=fixture();p['individualStocks'].append(p['individualStocks'][0])
        with self.assertRaises(ValueError):validate(p)
    def test_theme_weight_and_sources(self):
        p=fixture();codes=p['selectedStockCodes'][:2]
        review={'reviewedAt':p['reviewedAt'],'themes':[{'id':'t','name':'TEST','stockCodes':codes,'groupingBasis':'industry','reason':None,'membershipEvidence':[{'code':c,'sourceUrl':'https://example.org/member','fact':'TEST'} for c in codes]}]}
        p=enrich(p,review);self.assertEqual(p['themes'][0]['weightedChangeRate'],4)
        p['themes'][0]['weightedChangeRate']=5
        with self.assertRaisesRegex(ValueError,'weighted'):validate(p)
    def test_unknown_and_causality(self):
        p=fixture();self.assertTrue(all(x['reason'] is None for x in p['individualStocks']))
        p['individualStocks'][0]['reason']={'summary':'TEST','sourceUrl':'http://example.org','facts':['TEST'],'verificationStatus':'confirmed','causality':'source_attributed','publishedAt':p['asOf'],'checkedAt':p['reviewedAt']}
        with self.assertRaises(ValueError):validate(p)
    def test_twenty_ten_close(self):
        p=fixture('20:10');p['rankingProof']['allMarketRows'][0]['quotes']['NXT']['session']='NXT_CUMULATIVE'
        with self.assertRaisesRegex(ValueError,'NXT final'):validate(p)
    def test_threshold_tamper(self):
        p=fixture();p['selectedStockCodes'].pop()
        with self.assertRaisesRegex(ValueError,'>=4%'):validate(p)
    def test_five_slots_merge_and_replace(self):
        days={}
        for slot in SLOTS:
            p=fixture(slot);root,days=merge(p,days,dt.date(2026,11,16))
        self.assertEqual(len(days['2026-11-16']['editions']),5)
        root,days=merge(fixture(),days,dt.date(2026,11,16));self.assertEqual(len(days['2026-11-16']['editions']),5);self.assertEqual(root['slot'],'20:10')
    def test_calendar_four_days(self):
        days={d:{'date':d,'editions':{'13:40':fixture(date=d)}} for d in ['2026-11-12','2026-11-13','2026-11-14','2026-11-15']}
        root,retained=merge(fixture(),days,dt.date(2026,11,16))
        self.assertEqual(list(d['date'] for d in root['days']),['2026-11-16','2026-11-15','2026-11-14','2026-11-13'])
    def test_new_listing_unusable_base(self):
        p=fixture();r=p['rankingProof']['allMarketRows'][0];r['quotes']['KRX']['previousRegularClose']=None
        with self.assertRaises(Exception):validate(p)

if __name__=='__main__':unittest.main()

class AtomicPublication(unittest.TestCase):
    def test_conflict_remerge_readback_preserves_news(self):
        import json, urllib.error
        from publish_featured_v3 import publish
        versions={'h':{'market-briefing.json':{'unchanged':'news'}}};pending={};heads=['h'];n=[0];conflicts=[0]
        def api(method,path,body=None):
            if path=='git/ref/heads/main':return {'object':{'sha':heads[0]}}
            if method=='GET' and path.startswith('git/commits/'):return {'tree':{'sha':path.split('/')[-1]}}
            if method=='GET' and path.startswith('git/trees/'):
                return {'tree':[{'path':p} for p in versions[path.split('/')[-1].split('?')[0]]]}
            if path=='git/trees':
                n[0]+=1;key='t'+str(n[0]);v=copy.deepcopy(versions[body['base_tree']])
                for e in body['tree']:
                    if 'content' in e:v[e['path']]=json.loads(e['content'])
                    elif e.get('sha') is None:v.pop(e['path'],None)
                versions[key]=v;return {'sha':key}
            if path=='git/commits':
                key='c'+str(n[0]);versions[key]=copy.deepcopy(versions[body['tree']]);return {'sha':key}
            if method=='PATCH':
                if not conflicts[0]:
                    conflicts[0]+=1;versions['concurrent']=copy.deepcopy(versions['h']);versions['concurrent']['other-file.json']={'preserved':True};heads[0]='concurrent'
                    raise urllib.error.HTTPError('https://example.org',422,'conflict',{},None)
                heads[0]=body['sha'];return {}
            raise AssertionError(path)
        def read(path,ref='main',missing=False):return versions[heads[0] if ref=='main' else ref].get(path),None
        sha=publish(fixture(),api,read,clock=lambda:stamp('2026-11-16T13:42:00+09:00'))
        self.assertEqual(conflicts[0],1);self.assertEqual(versions[sha]['market-briefing.json'],{'unchanged':'news'})
        self.assertEqual(versions[sha]['other-file.json'],{'preserved':True});self.assertEqual(versions[sha]['featured-stocks.json']['status']['publication'],'success')
        self.assertEqual(versions[sha]['featured-stocks/2026-11-16.json']['editions']['13:40']['asOf'],fixture()['asOf'])

class ProductionGuards(unittest.TestCase):
    def test_legacy_publication_is_disabled(self):
        from publish_featured_stocks import publish
        with self.assertRaisesRegex(ValueError,'Legacy'):publish({'schemaVersion':2})
    def test_verified_holiday_never_calls_sources(self):
        from unittest.mock import patch
        import collection_worker as worker
        date='2026-11-16';request={'requestId':'holiday-test-only','releaseAt':date+'T13:40:00+09:00','evidence':{'tradingDayEvidence':{'date':date,'verified':True,'isTradingDay':False,'sourceUrl':'https://example.org/calendar','facts':['TEST ONLY HOLIDAY']}}}
        with patch.object(worker,'save') as save,patch.object(worker,'write_artifact'),patch.object(worker,'collect') as collect:
            result=worker.run(request)
        self.assertEqual(result['state'],'skipped_non_trading_day');collect.assert_not_called();save.assert_called_once()
    def test_index_four_day_validation(self):
        from featured_watch import index_matches
        p=fixture();index={'schemaVersion':3,'appVisibleCalendarDays':4,'releaseAt':p['releaseAt'],'asOf':p['asOf'],'dates':[{'date':'2026-11-16','path':'featured-stocks/2026-11-16.json'}]}
        self.assertTrue(index_matches(index,p));index['dates'][0]['path']='market-briefing.json';self.assertFalse(index_matches(index,p))

class CalculationAndReason(unittest.TestCase):
    def test_nonuniform_weighting(self):
        self.assertEqual(weighted([{'changeRate':4,'integratedTradeAmount':100},{'changeRate':8,'integratedTradeAmount':300}]),7)
    def test_confirmed_source_time_and_fact(self):
        p=fixture();r={'summary':'TEST ONLY CONFIRMED','sourceUrl':'https://example.org/original','publishedAt':'2026-11-16T13:39:00+09:00','checkedAt':p['reviewedAt'],'facts':['TEST ONLY FACT'],'verificationStatus':'confirmed','causality':'related_fact_only'}
        p['individualStocks'][0]['reason']=r;validate(p)
        p['individualStocks'][0]['reason']['publishedAt']='2026-11-16T13:41:00+09:00'
        with self.assertRaisesRegex(ValueError,'chronology'):validate(p)

class LiveAdapterContract(unittest.TestCase):
    def test_master_join_spac_and_outside_krx_top100(self):
        import os,pathlib,tempfile,json
        from unittest.mock import patch
        import featured_naver_v3 as adapter
        now=stamp('2026-11-16T13:40:00+09:00');krx=[];master=[]
        for i in range(1101):
            code=str(i).zfill(6);master.append({'code':code,'name':'TEST','groupCode':'ST','spacFlag':'Y' if i==1099 else 'N','preferredCode':'9' if i==1 else '0'})
            krx.append({'itemcode':code,'itemname':'TEST','type':'ST','sosok':'0','listedDate':'20200101'})
        codes=[str(i).zfill(6) for i in range(99)]+['001100']
        official={'totalCnt':100,'records':100,'total':1,'setTime':'2026-11-16 13:40','brdinfoTimeList':[{'isuSrdCd':'A'+c,'aggDd':'20261116','nowDd':'20261116'} for c in codes]}
        def fetch(url):
            code=url.split('/detail/')[1].split('/')[0];nxt=url.endswith('NXT')
            return {'itemcode':code,'tradeTime':'20261116134000','tradingSessionType':'REGULAR_MARKET','tradeAmount':str(1000000 if nxt and code=='001100' else 10000-int(code) if not nxt else 1),'nowPrice':'104','prevChangePrice':'4','prevChangeRate':'4'}
        original=os.getcwd()
        with tempfile.TemporaryDirectory() as temp:
            os.chdir(temp)
            try:
                pathlib.Path('collection-artifacts').mkdir()
                for name,rows in [('kospi',master),('kosdaq',[])]:pathlib.Path('collection-artifacts/'+name+'-master-probe.json').write_text(json.dumps({'rows':rows,'zipFileTimestamp':[2026,11,16,7,35,0],'sourceUrl':'https://example.org/master','retrievedAt':now.isoformat()}))
                with patch.object(adapter,'master_probe',return_value={'KOSPI':{},'KOSDAQ':{}}):package=adapter.normalize({'KRX':krx,'NXT_OFFICIAL':official},now.isoformat(),fetch,now=now)
                stocks,proof=rank_universe(package['securityMaster'],package['krxQuotes'],package['nxtQuotes'],package['coverage'],'2026-11-16',now,'13:40')
                self.assertEqual(stocks[0]['code'],'001100');self.assertNotIn('001099',{s['code'] for s in proof['allMarketRows']});self.assertEqual(stocks[2]['securityType'],'PREFERRED')
            finally:os.chdir(original)
