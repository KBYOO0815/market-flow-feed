import io
import unittest
import urllib.error
from unittest.mock import Mock
from source_http import read, CollectionFetch

class TransportTests(unittest.TestCase):
    def test_temporary_failure_retried_but_denial_not_retried(self):
        opener=Mock(side_effect=[urllib.error.HTTPError('',502,'bad',{},None),io.BytesIO(b'ok')])
        self.assertEqual(read('https://example.com',opener=opener,pause=Mock()),b'ok')
        self.assertEqual(opener.call_count,2)
        for code in (403,404):
            opener=Mock(side_effect=urllib.error.HTTPError('',code,'blocked',{},None))
            with self.assertRaises(urllib.error.HTTPError):read('https://example.com',opener=opener,pause=Mock())
            self.assertEqual(opener.call_count,1)
    def test_cache_deduplicates_without_cross_edition_carryover(self):
        fetch=Mock(return_value={'tradeAmount':123});c=CollectionFetch(fetch)
        c.prime(['a','a','b']);c('a');c('b');self.assertEqual(fetch.call_count,2)
        CollectionFetch(fetch)('a');self.assertEqual(fetch.call_count,3)
