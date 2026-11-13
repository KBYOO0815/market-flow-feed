import copy
import datetime as dt
import unittest
from unittest.mock import patch
import editorial_rules as r
import publish_feed as publisher
from prepare_feed import validate


def item(ident='one', region='foreign', scope=2, score=3):
    return {'id': ident, 'title': '검증용 공식 발표', 'summary': '테스트 전용 사실이며 실제 발행하지 않습니다.',
        'publishedAt': '2026-11-13T11:30:00+09:00', 'reviewedAt': '2026-11-13T11:40:00+09:00',
        'validUntil': '2026-11-13T14:50:00+09:00', 'reviewNote': 'fixture only',
        'sourceUrl': 'https://example.com/'+ident, 'reviewSourceUrl': 'https://example.com/'+ident,
        'sourceName': 'Test fixture', 'category': '기타', 'region': region,
        'kind': 'news', 'relatedStocks': [], 'impactRank': 1,
        'selection': {'eventKey': 'event-'+ident, 'eventAt': '2026-11-13T11:30:00+09:00',
            'newness': 'new', 'verificationStatus': 'confirmed', 'sourceClass': 'official',
            'materialType': 'event', 'scopeRank': scope,
            'scores': {key: score for key in r.SCORE_KEYS}, 'relatedEvidence': [],
            'facts': [{'key': 'fact-'+ident, 'occurredAt': '2026-11-13T11:30:00+09:00',
                       'statement': '공식 발표된 검증용 새 사실', 'sourceUrl': 'https://example.com/'+ident}]}}


def payload(items=None):
    items = [item()] if items is None else items
    return {'schemaVersion': 2, 'releaseAt': '2026-11-13T11:50:00+09:00',
        'asOf': '2026-11-13T11:40:00+09:00', 'items': items, 'tradingDayVerified': True,
        'calendarSourceUrl': 'https://example.com/calendar',
        'selectionAudit': {'mode': 'explicit', 'startAt': '2026-11-13T08:00:00+09:00', 'endAt': '2026-11-13T11:40:00+09:00'},
        'researchAudit': {'coverage': {topic: {'checkedAt': '2026-11-13T11:40:00+09:00', 'sourceUrls': ['https://example.com/test']}
            for topic in ('foreign_market','foreign_policy','foreign_technology','domestic_disclosures','domestic_policy','domestic_market')},
            'foreignCandidates': sum(i['region']=='foreign' for i in items),
            'domesticCandidates': sum(i['region']=='domestic' for i in items),
            'verifiedCandidates': len(items), 'duplicateExcluded': 0}}


def previous():
    old = payload()
    old.update(releaseAt='2026-11-13T08:50:00+09:00', asOf='2026-11-13T08:40:00+09:00')
    return old


class EditorialSelectionTests(unittest.TestCase):
    def test_valid_explicit_window_integrates_with_feed_validator(self):
        validate(payload())

    def test_new_article_time_cannot_relabel_old_fact(self):
        p = payload()
        p['items'][0]['selection']['eventAt'] = p['items'][0]['selection']['facts'][0]['occurredAt'] = '2026-11-13T07:59:59+09:00'
        with self.assertRaisesRegex(ValueError, 'outside'): validate(p)

    def test_since_previous_uses_actual_cutoff_and_excludes_boundary_repeats(self):
        p = payload()
        p['selectionAudit'].update(mode='since_previous', previousReleaseAt='2026-11-13T08:50:00+09:00', previousAsOf='2026-11-13T08:40:00+09:00', startAt='2026-11-13T08:40:00+09:00')
        old = previous()
        old['items'] = []
        r.validate_history(p, [old])
        p['selectionAudit']['previousAsOf'] = p['selectionAudit']['startAt'] = '2026-11-13T08:50:00+09:00'
        with self.assertRaisesRegex(ValueError, 'actual previous'): r.validate_history(p, [old])

    def test_same_fact_with_different_url_and_title_is_rejected(self):
        a, b = item('a'), item('b')
        b['selection']['facts'][0]['key'] = a['selection']['facts'][0]['key']
        with self.assertRaisesRegex(ValueError, 'same fact'): r.sort_payload(payload([a,b]))

    def test_one_event_requires_merged_facts_instead_of_separate_repeated_items(self):
        a, b = item('a'), item('b')
        b['selection']['eventKey'] = a['selection']['eventKey']
        with self.assertRaisesRegex(ValueError, 'same event'): r.sort_payload(payload([a,b]))
        a['selection']['facts'] += b['selection']['facts']
        validate(payload([a]))

    def test_already_published_fact_is_rejected_even_if_event_url_changes(self):
        p = payload()
        p['items'][0]['sourceUrl'] = 'https://example.com/reposted'
        with self.assertRaisesRegex(ValueError, 'already published fact'): r.validate_history(p, [previous()])

    def test_same_event_with_actual_new_followup_fact_is_allowed(self):
        p = payload()
        p['items'][0]['selection']['facts'][0]['key'] = 'new-official-action'
        with self.assertRaisesRegex(ValueError, 'followup'): r.validate_history(p, [previous()])
        p['items'][0]['selection']['newness'] = 'followup'
        r.validate_history(p, [previous()])

    def test_scope_before_product_and_independent_region_order(self):
        a,b,c,d = item('a',scope=2,score=5),item('b',scope=1,score=1),item('c',scope=2,score=2),item('d',region='domestic',scope=1,score=5)
        p = r.sort_payload(payload([d,c,a,b]))
        self.assertEqual([i['id'] for i in p['items']], ['b','a','c','d'])
        validate(p)
        p['items'][0],p['items'][1] = p['items'][1],p['items'][0]
        with self.assertRaisesRegex(ValueError, 'independently sorted'): r.validate_selection(p)

    def test_market_reaction_requires_visible_matching_observation_time(self):
        p = payload()
        i = p['items'][0]
        i.update(kind='market_snapshot', observedAt='2026-11-13T11:40:00+09:00', validUntil='2026-11-13T11:55:00+09:00',publishedAt='2026-11-13T11:40:00+09:00')
        i['selection'].update(materialType='market_trend',eventAt=i['observedAt'])
        i['selection']['facts'][0]['occurredAt'] = i['observedAt']
        with self.assertRaisesRegex(ValueError, 'visible'): validate(p)
        sorted_payload = r.sort_payload(p)
        validate(sorted_payload)
        self.assertIn('11:40 KST', sorted_payload['items'][0]['summary'])

    def test_related_stock_without_direct_evidence_is_rejected(self):
        p = payload()
        p['items'][0]['relatedStocks'] = ['TEST']
        with self.assertRaisesRegex(ValueError, 'direct source evidence'): validate(p)
        p['items'][0]['selection']['relatedEvidence'] = [{'stock':'TEST','sourceUrl':'https://example.com/relationship'}]
        validate(p)

    def test_rumours_and_nonpositive_relevance_score_are_rejected(self):
        p = payload()
        p['items'][0]['selection']['verificationStatus'] = 'rumour'
        with self.assertRaises(ValueError): validate(p)
        p = payload()
        p['items'][0]['selection']['scores']['koreaRelevance'] = 0
        with self.assertRaises(ValueError): validate(p)

    def test_requested_table_format_uses_actual_fact_time(self):
        result = r.markdown(payload())
        self.assertIn('11/13 08:00~11:40 KST 사이에 새로 확인된 재료', result)
        self.assertIn('## 국외 신규', result)
        self.assertIn('## 국내 신규', result)
        self.assertIn('| 1 | 11:30 |', result)

    def test_core_atomic_publisher_checks_pinned_history_before_writing(self):
        p = payload()
        calls = []
        def api(method, path, body=None):
            calls.append((method,path))
            if path == 'git/ref/heads/main': return {'object': {'sha':'pinned-head'}}
            if path.startswith('git/commits/'): return {'tree': {'sha':'tree'}}
            if path.startswith('git/trees/'): return {'tree': []}
            raise AssertionError('A duplicate reached a write: '+method+' '+path)
        def read(path, ref='main', missing=False):
            self.assertEqual(ref, 'pinned-head')
            return (previous() if path == 'morning-briefing.json' else None), 'sha'
        with patch.object(publisher,'api',side_effect=api), patch.object(publisher,'read_remote',side_effect=read):
            with self.assertRaisesRegex(ValueError, 'already published fact'): publisher.publish(p)
        self.assertTrue(all(method == 'GET' for method,path in calls))


if __name__ == '__main__': unittest.main()
