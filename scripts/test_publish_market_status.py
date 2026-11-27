import copy
import unittest
from datetime import date, datetime
from publish_market_status import KST, SLOTS, DRIVE_IDS, edition, eligible, process, session, validate


def payload(day="2026-11-28", market="2026-11-27"):
    return {"date": day, "slot": "07:11", "marketDate": market,
            "asOf": day + "T07:05:00+09:00",
            "content": [{"type":"text","value":"fixture"},
                        {"type":"metric","label":"fixture","value":1,"changePct":0},
                        {"type":"list","items":["fixture"]},
                        {"type":"table","columns":["A"],"rows":[[1]]},
                        {"type":"link","label":"fixture","url":"https://example.com/"}]}


def feed():
    return {"days": [], "navigation":{"previous":[],"today":[],"next":[]},
            "schedule":{"effectiveFrom":"2026-11-27","slots":list(SLOTS.values())}}


class TestPublisher(unittest.TestCase):
    def test_holiday_and_early_close(self):
        self.assertIsNone(session(date(2026,11,27),"us"))
        self.assertEqual(session(date(2026,11,28),"us").hour,3)
        self.assertIsNotNone(session(date(2026,11,27),"kr"))
        self.assertIsNone(session(date(2026,11,28),"kr"))

    def test_stale_rejected(self):
        now = datetime(2026,11,27,7,11,tzinfo=KST)
        with self.assertRaises(ValueError):
            eligible(payload("2026-11-27","2026-11-25"),"us",now)
        f = feed()
        process(f,"us",now,"fixture",lambda _: self.fail("holiday must not download"))
        self.assertEqual(f["navigation"]["today"][0]["state"],"skipped")
        self.assertEqual(f["days"],[])

    def test_publish_and_duplicate(self):
        now = datetime(2026,11,28,7,11,tzinfo=KST)
        f, p = feed(), payload()
        process(f,"us",now,"fixture",lambda _: p)
        e = f["days"][0]["editions"]["07:11"]
        self.assertEqual(e["content"],p["content"])
        self.assertEqual(e["display"]["sections"][3]["kind"],"bullets")
        self.assertEqual(len(e["sources"]),1)
        self.assertEqual(f["navigation"]["today"][0]["state"],"published")
        saved = copy.deepcopy(f)
        process(f,"us",now,"fixture",lambda _: self.fail("duplicate must not download"))
        self.assertEqual(f,saved)

    def test_missing_kr_and_bad_payload(self):
        f = feed()
        now = datetime(2026,11,27,15,41,tzinfo=KST)
        process(f,"kr",now,"")
        self.assertEqual(f["navigation"]["today"][1]["state"],"missing")
        p = payload()
        p["content"][0]["value"] = ""
        with self.assertRaises(ValueError):
            validate(p)

    def test_test_marker_and_future_observation(self):
        now = datetime(2026,11,28,7,11,tzinfo=KST)
        p = payload()
        p["content"][0]["title"] = "테스트: 시황"
        with self.assertRaises(ValueError):
            eligible(p,"us",now)
        p = payload()
        p["asOf"] = "2026-11-28T07:12:00+09:00"
        with self.assertRaises(ValueError):
            eligible(p,"us",now)

    def test_kr_drive_and_live_merge(self):
        self.assertEqual(DRIVE_IDS["kr"], "1bdjidvH5e--QmCX3_gde4p7vM6KEUhn3")
        self.assertNotEqual(DRIVE_IDS["us"], DRIVE_IDS["kr"])
        day = "2026-12-01"
        p = payload(day, day)
        p["slot"] = "15:41"
        p["asOf"] = day + "T15:35:00+09:00"
        now = datetime(2026,12,1,15,41,tzinfo=KST)
        f = feed()
        us = payload(day, "2026-11-30")
        process(f,"us",datetime(2026,12,1,7,11,tzinfo=KST),DRIVE_IDS["us"],lambda _: us)
        process(f,"kr",now,DRIVE_IDS["kr"],lambda _: p)
        self.assertEqual(set(f["days"][0]["editions"]), {"07:11", "15:41"})
        e = f["days"][0]["editions"]["15:41"]
        self.assertEqual(e["content"],p["content"])
        self.assertEqual(e["display"]["headline"],"한국 시황")
        self.assertEqual(f["navigation"]["today"][1]["state"],"published")
        saved = copy.deepcopy(f)
        process(f,"kr",now,DRIVE_IDS["kr"],lambda _: self.fail("duplicate must not download"))
        self.assertEqual(f,saved)

    def test_kr_test_date_and_stale(self):
        p = payload("2026-11-27","2026-11-27")
        p["slot"] = "15:41"
        p["asOf"] = "2026-11-27T15:30:00+09:00"
        with self.assertRaisesRegex(ValueError,"integration test date"):
            eligible(p,"kr",datetime(2026,11,27,15,51,tzinfo=KST))
        with self.assertRaisesRegex(ValueError,"stale"):
            eligible(p,"kr",datetime(2026,11,30,15,41,tzinfo=KST))


if __name__ == "__main__":
    unittest.main()
