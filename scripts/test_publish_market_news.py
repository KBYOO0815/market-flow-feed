import datetime as dt
import unittest
from copy import deepcopy
from publish_market_news import KST, validate, merge, filename, session_for, matching_ids

DAY = dt.date(2026, 11, 28)
NOW = dt.datetime(2026, 11, 28, 8, 1, tzinfo=KST)
BASE = {"date": str(DAY), "slot": "08:00", "asOf": "2026-11-28T07:50:00+09:00", "foreignNews": [], "domesticNews": []}
FEED = {"schemaVersion": 1, "days": [], "navigation": {"previous": [], "today": [], "next": []}}
ITEM = {"id": "fixture", "title": "Fixture", "summary": "Fixture", "sourceName": "Fixture", "sourceUrl": "https://example.com/fixture", "publishedAt": "2026-11-28T07:00:00+09:00", "checkedAt": "2026-11-28T07:51:00+09:00", "relatedStocks": [], "impactRank": 1, "category": "fixture", "region": "foreign", "eventKey": "fixture", "factKey": "fixture"}

class NewsTests(unittest.TestCase):
    def test_filename(self):
        self.assertEqual(filename(DAY, "08:00"), "market-news-2026-11-28-0800.json")
    def test_public_folder_exact_name(self):
        html = '<a href="https://drive.google.com/file/d/abcdefghijk/view"><div>market-news-2026-11-28-0800.json</div></a><a href="https://drive.google.com/file/d/zzzzzzzzzzz/view">market-news-2026-11-28-0800.json.bak</a>'
        self.assertEqual(matching_ids(html, filename(DAY, "08:00")), ["abcdefghijk"])
    def test_public_folder_duplicates(self):
        html = '<a href="/file/d/abcdefghijk/view">market-news-2026-11-28-0800.json</a><a href="/file/d/zzzzzzzzzzz/view">market-news-2026-11-28-0800.json</a>'
        self.assertEqual(matching_ids(html, filename(DAY, "08:00")), ["abcdefghijk", "zzzzzzzzzzz"])
    def test_empty_valid(self):
        self.assertEqual(validate(BASE, DAY, "08:00", NOW)["foreignNews"], [])
    def test_test_marker(self):
        with self.assertRaises(ValueError):
            validate(dict(BASE, testOnly=True), DAY, "08:00", NOW)
    def test_stale(self):
        with self.assertRaises(ValueError):
            validate(dict(BASE, asOf="2026-11-28T07:49:00+09:00"), DAY, "08:00", NOW)
    def test_wrong_slot(self):
        with self.assertRaises(ValueError):
            validate(BASE, DAY, "15:20", NOW)
    def test_item(self):
        self.assertEqual(validate(dict(BASE, foreignNews=[ITEM]), DAY, "08:00", NOW)["foreignNews"], [ITEM])
    def test_invalid_item(self):
        with self.assertRaises(ValueError):
            validate(dict(BASE, foreignNews=[dict(ITEM, sourceUrl="http://example.com")]), DAY, "08:00", NOW)
    def test_duplicate(self):
        with self.assertRaises(ValueError):
            validate(dict(BASE, foreignNews=[ITEM, dict(ITEM, impactRank=2)]), DAY, "08:00", NOW)
    def test_merge(self):
        e = validate(BASE, DAY, "08:00", NOW)
        f = merge(FEED, DAY, "08:00", NOW, e)
        self.assertEqual([n["state"] for n in f["navigation"]["today"]], ["published", "scheduled"])
        self.assertEqual(merge(f, DAY, "08:00", NOW, e), f)
        self.assertEqual(session_for(f, DAY, "08:00"), e)
    def test_failure_preserves_previous(self):
        f = deepcopy(FEED)
        f["days"] = [{"date": "2026-11-26", "sessions": [{"slot": "07:40"}]}, {"date": "2026-11-27", "sessions": [{"slot": "15:40"}]}]
        out = merge(f, DAY, "08:00", NOW, failure="missing")
        self.assertEqual([d["date"] for d in out["days"]], ["2026-11-27"])
        self.assertEqual(out["navigation"]["today"][0]["state"], "failed")
        self.assertEqual(out["navigation"]["previous"][0]["state"], "published")

if __name__ == "__main__":
    unittest.main()
