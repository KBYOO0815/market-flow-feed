import copy
import unittest
from datetime import date, datetime
from publish_market_status import KST, SLOTS, DRIVE_IDS, edition, eligible, market_day, process, session, validate, filename, load_current


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
        self.assertEqual(market_day(date(2026,11,27),"us"),date(2026,11,25))
        self.assertIsNone(session(date(2026,11,29),"us"))
        self.assertEqual(market_day(date(2026,11,30),"us"),date(2026,11,27))
        self.assertEqual(session(date(2026,11,28),"us").hour,3)
        self.assertIsNotNone(session(date(2026,11,27),"kr"))
        self.assertIsNone(session(date(2026,11,28),"kr"))

    def test_stale_rejected(self):
        now = datetime(2026,11,27,7,11,tzinfo=KST)
        with self.assertRaises(ValueError):
            eligible(payload("2026-11-27","2026-11-25"),"us",now)
        f = feed()
        process(f,"us",datetime(2026,11,29,7,11,tzinfo=KST),"fixture",
                lambda _: self.fail("Sunday must not download"))
        self.assertEqual(f["navigation"]["today"][0]["state"],"skipped")
        self.assertEqual(f["days"],[])

    def test_publish_and_duplicate(self):
        now = datetime(2026,11,28,7,11,tzinfo=KST)
        f, p = feed(), payload()
        process(f,"us",now,"fixture",lambda _: p)
        e = f["days"][0]["editions"]["07:11"]
        self.assertEqual(e["content"],p["content"])
        self.assertEqual(e["display"]["sections"][3]["kind"],"bullets")
        self.assertEqual(e["sources"], [{"name":"fixture","url":"https://example.com/"}])
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
        self.assertEqual(DRIVE_IDS["kr"], "kr")
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

    def test_us_monday_and_holiday_publish(self):
        for day, market in (("2026-11-30","2026-11-27"), ("2026-12-26","2026-12-24")):
            with self.subTest(day=day):
                p = payload(day,market)
                now = datetime.fromisoformat(day+"T07:11:00+09:00")
                f = feed()
                process(f,"us",now,DRIVE_IDS["us"],lambda _: p)
                e = f["days"][0]["editions"]["07:11"]
                self.assertEqual(e["marketDate"],market)
                self.assertEqual(e["content"],p["content"])
                self.assertEqual(f["navigation"]["today"][0]["state"],"published")
                self.assertIn(market,e["display"]["badges"][0])
                stale = copy.deepcopy(p)
                stale["asOf"] = market+"T23:59:00+09:00"
                with self.assertRaises(ValueError):
                    eligible(stale,"us",now)

    def test_us_wrong_market_date_and_stale_report(self):
        now = datetime(2026,11,30,7,11,tzinfo=KST)
        with self.assertRaisesRegex(ValueError,"marketDate"):
            eligible(payload("2026-11-30","2026-11-29"),"us",now)
        with self.assertRaisesRegex(ValueError,"stale"):
            eligible(payload(),"us",now)


    def test_dated_lookup(self):
        now = datetime(2026,11,28,7,11,tzinfo=KST)
        name = filename(now.date(), "us")
        self.assertEqual(name, "market-status-2026-11-28-0711.json")
        html = '<a href="https://drive.google.com/file/d/abcdefghijk/view">' + name + '</a>'
        self.assertEqual(load_current("us", now, lambda: html, lambda _: payload()), payload())
        with self.assertRaisesRegex(ValueError, "not found"):
            load_current("us", now, lambda: "", lambda _: payload())
        with self.assertRaisesRegex(ValueError, "No eligible"):
            load_current("us", now, lambda: html, lambda _: dict(payload(), testOnly=True))


if __name__ == "__main__":
    unittest.main()
