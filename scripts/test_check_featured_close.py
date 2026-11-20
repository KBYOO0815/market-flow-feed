"""Tests for session-aware read-only price audits."""
import copy
import unittest

from check_featured_close import validate


def row(code, session="REGULAR", price=110, prior=100, date="2026-11-20"):
    market = "NXT" if session == "PRE" else "KRX"
    observed = ("08:39:00" if session == "PRE" else
                "19:59:00" if session == "AFTER" else "15:29:00")
    return {
        "code": code,
        "price": price,
        "previousRegularClose": prior,
        "changeRate": (price / prior - 1) * 100,
        "rateMarket": market,
        "priceMarket": market,
        "priceSession": session,
        "priceObservedAt": date + "T" + observed + "+09:00",
        "comparison": {"eligible": True},
    }


def sample(date="2026-11-20", with_pre=False):
    def edition(slot, session, price):
        rows = [row("{:06d}".format(i+1), session, price=price, date=date) for i in range(100)]
        return {"date": date, "rateBasis": "KRX_PREVIOUS_CLOSE",
                "priceSession": session, "stocks": rows}
    editions = {
        "15:40": edition("15:40", "REGULAR", 110),
        "20:10": edition("20:10", "AFTER", 120),
    }
    if with_pre:
        editions["08:40"] = edition("08:40", "PRE", 105)
    return {"date": date, "editions": editions}


class FeaturedCloseTest(unittest.TestCase):
    def test_regular_and_after_market_prices_are_expected_to_differ(self):
        self.assertEqual(validate(sample()), [])

    def test_previous_regular_close_must_match(self):
        data = sample()
        data["editions"]["20:10"]["stocks"][1]["previousRegularClose"] = 90
        self.assertTrue(any("previousRegularClose differs" in x for x in validate(data)))

    def test_after_rate_formula_must_match(self):
        data = sample()
        data["editions"]["20:10"]["stocks"][2]["changeRate"] = 19
        self.assertTrue(any("changeRate formula differs" in x for x in validate(data)))

    def test_after_market_must_not_use_future_trade(self):
        data = sample()
        data["editions"]["20:10"]["stocks"][3]["priceObservedAt"] = "2026-11-20T20:05:00+09:00"
        self.assertTrue(any("outside after-market" in x for x in validate(data)))

    def test_pre_market_requires_nxt(self):
        data = sample(with_pre=True)
        data["editions"]["08:40"]["stocks"][4]["priceMarket"] = "KRX"
        self.assertTrue(any("must be from NXT PRE" in x for x in validate(data)))

    def test_price_session_must_match_slot(self):
        data = sample()
        data["editions"]["20:10"]["priceSession"] = "REGULAR"
        self.assertTrue(any("priceSession is not AFTER" in x for x in validate(data)))

    def test_skip_missing_evening_session(self):
        data = sample()
        del data["editions"]["20:10"]
        self.assertEqual(validate(data), [])

    def test_historical_legacy_session_metadata_not_required(self):
        data = sample(date="2026-11-18")
        del data["editions"]["15:40"]["priceSession"]
        del data["editions"]["20:10"]["priceSession"]
        self.assertEqual(validate(data), [])


if __name__ == "__main__":
    unittest.main()
