import datetime as dt
import unittest
from unittest.mock import Mock, patch
import featured_watch as w
import test_featured_stocks as fixtures


class FeaturedWatchTests(unittest.TestCase):
    def draft(self): return fixtures.enrich(fixtures.fixture(),fixtures.reviewed())
    def index(self,draft):
        return {'schemaVersion':1,'appVisibleCalendarDays':2,'releaseAt':draft['releaseAt'],'asOf':draft['asOf'],
                'visibleUntil':'2026-11-14T00:00:00+09:00',
                'dates':[{'date':'2026-11-12','path':'featured-stocks/2026-11-12.json'}]}

    def test_queue_delay_uses_creation_time_original_slot(self):
        created=dt.datetime(2026,11,13,9,41,tzinfo=w.KST)
        self.assertEqual(w.scheduled_release(created,'40 0,2,4,6 * * 1-5').strftime('%H:%M'),'09:40')
        with self.assertRaises(ValueError):w.scheduled_release(created,'unknown')

    def test_waits_for_reviewed_draft_then_verifies_all_three_files(self):
        draft=self.draft();release=w.stamp(draft['releaseAt']);now=[release];records=[]
        def read(path,ref='main',missing=False):
            if ref=='commit':
                if path=='featured-stocks.json':return draft,'sha'
                if path.endswith('index.json'):return self.index(draft),'sha'
                return {'editions':{'09:40':draft}},'sha'
            if path.startswith('drafts/') and now[0]>release:return draft,'sha'
            return None,None
        def pause(seconds):now[0]+=dt.timedelta(seconds=seconds)
        write=Mock(return_value='commit')
        result=w.watch(release,records.append,read,write,lambda:now[0],pause)
        self.assertEqual(result['state'],'published');self.assertTrue(result['published']);write.assert_called_once_with(draft)

    def test_missing_draft_is_recorded_as_missed_without_fabrication(self):
        release=w.stamp('2026-11-13T09:40:00+09:00');now=[release+dt.timedelta(minutes=29,seconds=59)];records=[];write=Mock()
        def pause(seconds):now[0]+=dt.timedelta(seconds=max(seconds,1))
        with self.assertRaisesRegex(RuntimeError,'missed'):
            w.watch(release,records.append,lambda *a,**k:(None,None),write,lambda:now[0],pause)
        self.assertEqual(records[-1]['state'],'publication_missed');self.assertFalse(records[-1]['published']);write.assert_not_called()

    def test_probe_draft_is_rejected_even_when_matching_release(self):
        draft=self.draft();draft['probeOnly']=True;release=w.stamp(draft['releaseAt']);now=[release+dt.timedelta(minutes=29,seconds=59)];records=[];write=Mock()
        def read(path,*a,**k):return (draft if path.startswith('drafts/') else None),None
        def pause(seconds):now[0]+=dt.timedelta(seconds=max(seconds,1))
        with self.assertRaises(RuntimeError):w.watch(release,records.append,read,write,lambda:now[0],pause)
        self.assertIn('not publishable',records[-1]['lastIssue']);write.assert_not_called()

    def test_index_mismatch_cannot_be_reported_as_success(self):
        draft=self.draft();release=w.stamp(draft['releaseAt']);records=[]
        def read(path,ref='main',missing=False):
            if path.startswith('drafts/'):return draft,'sha'
            if ref=='commit':
                if path=='featured-stocks.json':return draft,'sha'
                if path.endswith('index.json'):return {},'sha'
                return {'editions':{'09:40':draft}},'sha'
            return None,None
        with self.assertRaisesRegex(RuntimeError,'readback mismatch'):
            w.watch(release,records.append,read,lambda x:'commit',lambda:release,Mock())
        self.assertEqual(records[-1]['state'],'publication_failed');self.assertFalse(records[-1]['published'])

    def test_already_published_current_slot_needs_index_match(self):
        draft=self.draft();release=w.stamp(draft['releaseAt']);records=[];write=Mock()
        def read(path,*a,**k):
            if path=='featured-stocks.json':return draft,'sha'
            if path.endswith('index.json'):return self.index(draft),'sha'
            return {'editions':{'09:40':draft}},'sha'
        result=w.watch(release,records.append,read,write,lambda:release+dt.timedelta(hours=1),Mock())
        self.assertTrue(result['alreadyPublished']);write.assert_not_called()

    def test_empty_or_wrong_app_index_cannot_hide_missing_visible_edition(self):
        draft=self.draft();good=self.index(draft)
        self.assertTrue(w.index_matches(good,draft))
        for rows in ([],[{'date':'2026-11-12','path':'briefings/2026-11-12.json'}],[{'date':'2026-11-09','path':'featured-stocks/2026-11-09.json'}]):
            self.assertFalse(w.index_matches({**good,'dates':rows},draft))

    def test_code_change_without_draft_is_safe_no_publication(self):
        with patch.dict(w.os.environ,{'GITHUB_REPOSITORY':'KBYOO0815/market-flow-feed','EVENT_SCHEDULE':''}),patch.object(w,'read_remote',return_value=(None,None)),patch.object(w,'watch') as watch:
            w.main();watch.assert_not_called()


if __name__=='__main__':unittest.main()
