import unittest
from unittest.mock import patch
import collection_worker as w

class WorkerTests(unittest.TestCase):
    def test_failure_records_reason_without_publishing(self):
        records=[]
        with patch.object(w,'save',side_effect=lambda x:records.append({k:dict(v) for k,v in x.items()})),patch.object(w,'collect',side_effect=ValueError('source failed')):
            with self.assertRaises(ValueError):w.run({'requestId':'test-failure','releaseAt':'invalid','evidence':{}})
        last=next(iter(records[-1].values()))
        self.assertEqual(last['state'],'collection_failed');self.assertFalse(last['published'])
        self.assertEqual(last['error'],'source failed')
        self.assertTrue(all(p.startswith('operations/') for r in records for p in r))
    def test_success_stores_snapshot_not_public_feed(self):
        records=[]
        with patch.object(w,'save',side_effect=lambda x:records.append(dict(x))),patch.object(w,'collect',return_value={'stocks':[{}]*50}):
            w.run({'requestId':'test-success','releaseAt':'invalid','evidence':{}})
        self.assertEqual(records[-1]['operations/collections/test-success.json']['state'],'collected')
        self.assertIn('collections/featured-stocks/test-success.json',records[-1])
        self.assertNotIn('featured-stocks.json',records[-1])
    def test_invalid_request_id_does_not_write(self):
        with patch.object(w,'save') as save:
            with self.assertRaises(ValueError):w.run({'requestId':'../escape'})
            save.assert_not_called()
