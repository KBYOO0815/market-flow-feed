import unittest
import datetime as dt
from publish_featured_stocks import edition, merge, normalize, KST, TEST_DAY

DAY = dt.date(2026, 11, 30)
NOW = dt.datetime(2026, 11, 30, 9, 40, tzinfo=KST)
BASE = {"date": str(DAY), "slot":"09:40", "asOf":"2026-11-30T09:35:00+09:00",
        "marketSummary":"fixture", "themes":[{"name":"테마","catalyst":"재료",
        "stocks":[{"name":"A","change":"상한가"},{"name":"B","change":"+25~27%대"}],
        "sources":["https://example.com/source"]}], "individualStocks":[], "outlook":"fixture"}
class Tests(unittest.TestCase):
    def test_alias_and_text(self):
        e = edition(BASE, DAY, "09:40", NOW)
        self.assertEqual(e["analysis"]["themes"][0]["stocks"][0]["changeRate"], "상한가")
        self.assertIn("+25~27%대", e["themes"][1]["reason"]["summary"])
        self.assertEqual(e["stocks"], [])
        self.assertEqual(e["themes"][1]["stockCodes"], [])
        self.assertNotIn("weightedChangeRate", e["themes"][1])
    def test_test_flag(self):
        with self.assertRaises(ValueError):
            normalize(dict(BASE, testOnly=True), DAY, "09:40", NOW)
        self.assertTrue(edition(BASE, DAY, "09:40", NOW, test=True)["testOnly"])
    def test_wrong_date(self):
        with self.assertRaises(ValueError):
            normalize(BASE, TEST_DAY, "09:40", NOW)
    def test_stale(self):
        with self.assertRaises(ValueError):
            normalize(dict(BASE, asOf="2026-11-30T09:29:00+09:00"), DAY, "09:40", NOW)
    def test_late(self):
        with self.assertRaises(ValueError):
            normalize(dict(BASE, asOf="2026-11-30T09:41:00+09:00"), DAY, "09:40", NOW)
    def test_source(self):
        import copy
        d = copy.deepcopy(BASE)
        d["themes"][0]["sources"] = []
        with self.assertRaises(ValueError):
            normalize(d, DAY, "09:40", NOW)
        self.assertEqual(normalize(d, DAY, "09:40", NOW, test=True)["themes"][0]["sources"], [])
    def test_merge(self):
        f = {"schemaVersion":1,"days":{},"navigation":{"previous":[],"today":[],"next":[]}}
        e = edition(BASE, DAY, "09:40", NOW)
        out = merge(f, DAY, "09:40", NOW, e)
        self.assertEqual(out["days"][str(DAY)]["editions"]["09:40"], e)
        self.assertEqual([r["state"] for r in out["navigation"]["today"]], ["published","scheduled"])
        self.assertEqual(merge(out, DAY, "09:40", NOW, e), out)
