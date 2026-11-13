import datetime as dt
import unittest
import urllib.error
from unittest.mock import Mock, patch, mock_open
import briefing_watch as watcher
import operation_store as store
from prepare_feed import KST

class PublicationConflicts(unittest.TestCase):
    def test_conflict_rechecks_actual_root_instead_of_reporting_false_failure(self):
        release = dt.datetime(2026, 11, 13, 20, 20, tzinfo=KST)
        payload = {'releaseAt': release.isoformat(), 'asOf': release.isoformat(), 'items': []}
        state = {'written': False}
        def read(path, *a, **k):
            if path.startswith('drafts'): return payload, 'draft'
            if state['written']:
                return (payload if path.startswith('morning') else {'editions': {'20:20': payload}}), 'sha'
            return None, None
        def write(value):
            state['written'] = True
            raise urllib.error.HTTPError('', 422, 'non-fast-forward', {}, None)
        with patch.object(watcher, 'prepare', return_value=payload), patch('editorial_rules.active', return_value=False):
            result = watcher.watch(release, Mock(), read, write, lambda: release, Mock())
        self.assertEqual(result['state'], 'published')
        self.assertTrue(result['alreadyPublished'])
    def test_operation_conflict_fetches_latest_head_and_backs_off(self):
        attempts = []
        def api(method, path, body=None):
            if path == 'git/ref/heads/main': return {'object': {'sha': 'head'}}
            if path == 'git/commits/head': return {'tree': {'sha': 'base'}}
            if method == 'PATCH':
                attempts.append(body)
                if len(attempts) < 4: raise urllib.error.HTTPError('', 422, 'race', {}, None)
            return {'sha': 'new'}
        with patch.object(store, 'api', side_effect=api), patch.object(store.time, 'sleep') as pause, patch.object(store.os, 'makedirs'), patch('builtins.open', mock_open()):
            store.save('operations/publications/test.json', {'state': 'published'})
        self.assertEqual(len(attempts), 4)
        self.assertEqual(pause.call_count, 3)
