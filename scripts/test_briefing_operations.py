import datetime as dt
from email.message import Message
import io
import unittest
import urllib.error
from unittest.mock import Mock, patch
import briefing_preflight as preflight
import briefing_watch as watcher
from briefing_schedule import resolve
from prepare_feed import KST, validate
import test_prepare_feed


class Response(io.BytesIO):
    status = 200
    headers = Message()


class SourceChecks(unittest.TestCase):
    def test_dart_explicit_date_and_zero_filings_are_a_valid_empty_result(self):
        date = dt.date(2026, 11, 13)
        dart = preflight.sources(date)['domestic_disclosures'][0]
        self.assertIn('selectDate=2026.11.13', dart)
        record = preflight.fetch_source(dart, date, opener=Mock(return_value=Response('전체 0 건 (2026년 11월 13일)'.encode())), pause=Mock())
        self.assertTrue(record['available'])
        self.assertEqual(record['filingCount'], 0)

    def test_stale_dart_date_is_not_today_empty_and_is_rechecked(self):
        opener = Mock(side_effect=lambda *a, **k: Response('전체 0 건 (2026년 11월 12일)'.encode()))
        result = preflight.fetch_source(preflight.sources(dt.date(2026, 11, 13))['domestic_disclosures'][0], dt.date(2026, 11, 13), opener=opener, pause=Mock())
        self.assertFalse(result['available'])
        self.assertEqual(len(result['attempts']), 2)
        self.assertIn('stale selected date', result['attempts'][0]['error'])

    def test_access_denial_recorded_without_retry_or_bypass(self):
        opener = Mock(side_effect=urllib.error.HTTPError('', 403, 'Forbidden', {}, None))
        result = preflight.fetch_source('https://example.com', dt.date(2026, 11, 13), opener=opener, pause=Mock())
        self.assertFalse(result['available'])
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(result['attempts'][0]['httpStatus'], 403)

    def test_transient_failure_then_success_records_both_attempts(self):
        opener = Mock(side_effect=[TimeoutError('timeout'), Response(b'<html>ok</html>')])
        result = preflight.fetch_source('https://example.com', dt.date(2026, 11, 13), opener=opener, pause=Mock())
        self.assertTrue(result['available'])
        self.assertEqual(len(result['attempts']), 2)

    def test_one_topic_failure_does_not_cancel_remaining_topics_or_certify_research(self):
        calls = []
        def fetch(url, date):
            calls.append(url)
            return {'available': not ('dart.' in url or 'kind.' in url), 'candidates': []}
        result = preflight.collect(dt.datetime(2026, 11, 13, 6, 40, tzinfo=KST), fetch)
        self.assertEqual(len(result['sources']), 6)
        self.assertEqual(len(calls), sum(map(len, preflight.sources(dt.date(2026, 11, 13)).values())))
        self.assertIn('domestic_disclosures', result['unavailableTopics'])
        self.assertFalse(result['editorialCoverageVerified'])
        self.assertFalse(result['tradingDayVerified'])


class EditionOperations(unittest.TestCase):
    def test_recovery_cannot_include_news_first_published_after_original_release(self):
        payload = test_prepare_feed.EditorialFreshnessTests().payload(7, 40)
        payload['asOf'] = '2026-11-11T07:50:00+09:00'
        payload['items'][0]['reviewedAt'] = payload['asOf']
        payload['items'][0]['publishedAt'] = '2026-11-11T07:44:00+09:00'
        with self.assertRaisesRegex(ValueError, 'after target releaseAt'):
            validate(payload)
    def test_delayed_publisher_keeps_original_cron_slot(self):
        now = dt.datetime(2026, 11, 13, 8, 55, tzinfo=KST)
        self.assertEqual(resolve(now, '40 21,22 * * 0-4').strftime('%H:%M'), '07:40')
        self.assertEqual(resolve(now, '35 23 * * 0-4', preflight=True).strftime('%H:%M'), '08:50')

    def test_unknown_schedule_requires_explicit_target(self):
        with self.assertRaises(ValueError):
            resolve(dt.datetime.now(KST), 'unknown')

    def test_delayed_job_accepts_verified_archive_without_rolling_back_newer_root(self):
        release = dt.datetime(2026, 11, 11, 6, 40, tzinfo=KST)
        archived = {'releaseAt': release.isoformat(), 'items': []}
        root = {'releaseAt': (release+dt.timedelta(hours=1)).isoformat(), 'items': []}
        def read(path, *a, **k):
            return (root if path.startswith('morning') else {'editions': {'06:40': archived}}), 'sha'
        write = Mock()
        result = watcher.watch(release, Mock(), read, write, lambda: release+dt.timedelta(hours=2), Mock())
        self.assertTrue(result['alreadyPublished'])
        write.assert_not_called()

    def test_waits_for_late_draft_without_relabelling_old_edition(self):
        release = dt.datetime(2026, 11, 11, 7, 40, tzinfo=KST)
        now = [release]
        new = {'releaseAt': release.isoformat(), 'asOf': release.isoformat(), 'items': []}
        old = {'releaseAt': (release-dt.timedelta(hours=1)).isoformat()}
        published, records = [], []
        def read(path, ref='main', missing=False):
            if ref == 'commit':
                return (new if path.startswith('morning') else {'editions': {'07:40': new}}), 'sha'
            if path.startswith('morning'): return old, 'sha'
            if path.startswith('briefings/'): return None, None
            return (new if now[0] > release else old), 'sha'
        def pause(seconds): now[0] += dt.timedelta(seconds=seconds)
        def write(payload): published.append(payload); return 'commit'
        with patch.object(watcher, 'prepare', side_effect=lambda draft, now: draft):
            result = watcher.watch(release, records.append, read, write, lambda: now[0], pause)
        self.assertEqual(result['state'], 'published')
        self.assertEqual(published, [new])
        self.assertEqual(records[-1]['state'], 'published')

    def test_missing_draft_times_out_and_is_recorded_without_publication(self):
        release = dt.datetime(2026, 11, 11, 6, 40, tzinfo=KST)
        now = [release+dt.timedelta(minutes=29, seconds=59)]
        records, write = [], Mock()
        def pause(seconds): now[0] += dt.timedelta(seconds=max(seconds, 1))
        with self.assertRaisesRegex(RuntimeError, 'No publishable draft'):
            watcher.watch(release, records.append, lambda *a, **k: (None, None), write, lambda: now[0], pause)
        write.assert_not_called()
        self.assertEqual(records[-1]['state'], 'publication_missed')

    def test_old_or_unreviewed_draft_is_never_published(self):
        release = dt.datetime(2026, 11, 11, 6, 40, tzinfo=KST)
        now = [release+dt.timedelta(minutes=29, seconds=59)]
        write, records = Mock(), []
        draft = {'releaseAt': release.isoformat()}
        def read(path, *a, **k): return (draft if path.startswith('drafts') else None), None
        def pause(seconds): now[0] += dt.timedelta(seconds=max(seconds, 1))
        with self.assertRaises(RuntimeError):
            watcher.watch(release, records.append, read, write, lambda: now[0], pause)
        write.assert_not_called()
        self.assertIn('draft_validation_failed', records[-1]['lastIssue'])

    def test_readback_mismatch_records_failure(self):
        release = dt.datetime(2026, 11, 11, 7, 40, tzinfo=KST)
        draft = {'releaseAt': release.isoformat(), 'asOf': release.isoformat(), 'items': []}
        def read(path, *a, **k): return (draft if path.startswith('drafts') else {}), None
        records = []
        with patch.object(watcher, 'prepare', return_value=draft), self.assertRaisesRegex(RuntimeError, 'readback mismatch'):
            watcher.watch(release, records.append, read, lambda x: 'commit', lambda: release, Mock())
        self.assertEqual(records[-1]['state'], 'publication_failed')


if __name__ == '__main__': unittest.main()
