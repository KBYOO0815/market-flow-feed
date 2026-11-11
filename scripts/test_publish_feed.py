"""Publication invariants: one commit, retained archives, concurrent update safety."""
import base64
import copy
import json
import unittest
import urllib.error
from unittest.mock import patch
import publish_feed as p


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.early = {'releaseAt': '2026-11-11T07:30:00+09:00', 'asOf': '2026-11-11T07:20:00+09:00', 'items': []}
        self.late = {'releaseAt': '2026-11-11T15:30:00+09:00', 'asOf': '2026-11-11T15:25:00+09:00', 'items': []}
        self.archive = {'date': '2026-11-11', 'editions': {'07:30': self.early}}

    def test_archive_preserves_previous_editions_and_replaces_only_corrected_slot(self):
        _, day = p.archive_update(self.late, self.archive)
        self.assertEqual(day['editions']['07:30'], self.early)
        self.assertEqual(day['editions']['15:30'], self.late)
        self.assertEqual(list(self.archive['editions']), ['07:30'])
        with self.assertRaises(ValueError):
            p.archive_update(self.late, {'date': '2026-11-10'})

    def test_atomic_commit_retries_concurrent_main_without_losing_another_edition(self):
        calls, generation = [], [0]
        def api(method, path, body=None):
            calls.append((method, path, copy.deepcopy(body)))
            if path == 'git/ref/heads/main': return {'object': {'sha': 'head'+str(generation[0])}}
            if path.startswith('git/commits/head'): return {'tree': {'sha': 'tree'+str(generation[0])}}
            if method == 'GET' and path.startswith('contents/'):
                content = self.early if path.startswith('contents/morning') else self.archive
                if generation[0] and path.startswith('contents/briefings'):
                    content = copy.deepcopy(content)
                    content['editions']['11:30'] = {'releaseAt':'2026-11-11T11:30:00+09:00'}
                if 'newcommit' in path:
                    entries = [c[2]['tree'] for c in calls if c[:2] == ('POST','git/trees')][-1]
                    name = path.split('contents/')[1].split('?')[0]
                    content = json.loads(next(e['content'] for e in entries if e['path'] == name))
                return {'content': base64.b64encode(json.dumps(content).encode()).decode(), 'sha': 'blob'}
            if path == 'git/trees': return {'sha':'newtree'}
            if path == 'git/commits': return {'sha':'newcommit'+str(generation[0])}
            if path == 'git/refs/heads/main':
                self.assertFalse(body['force'])
                if generation[0] == 0:
                    generation[0] = 1
                    raise urllib.error.HTTPError('',422,'non-fast-forward',{},None)
                return {}
            raise AssertionError((method,path))
        with patch.object(p, 'api', side_effect=api):
            self.assertEqual(p.publish(self.late),'newcommit1')
        trees = [c[2] for c in calls if c[:2] == ('POST','git/trees')]
        self.assertEqual(len(trees),2)
        self.assertEqual(trees[-1]['base_tree'],'tree1')
        entries = {e['path']:json.loads(e['content']) for e in trees[-1]['tree']}
        self.assertEqual(entries['morning-briefing.json'],self.late)
        self.assertEqual(entries['briefings/2026-11-11.json']['editions']['15:30'],self.late)
        self.assertIn('11:30', entries['briefings/2026-11-11.json']['editions'])

    def test_newer_published_root_cannot_be_rolled_back(self):
        with patch.object(p,'api',side_effect=[{'object':{'sha':'h'}},{'tree':{'sha':'t'}}]), patch.object(p,'read_remote',return_value=(self.late,'s')):
            self.assertIsNone(p.publish(self.early))

if __name__ == '__main__': unittest.main()
