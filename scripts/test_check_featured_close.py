"""Tests for read-only 15:40/20:10 KRX close comparisons."""
import copy
import unittest

from check_featured_close import validate


def row(code, price=110, prior=100):
    return {
        "code": code,
        "price": price,
        "previousRegularClose": prior,
        "changeRate": (price / prior - 1) * 100,
        "rateMarket": "KRX",
        "comparison": {"eligible": True},
    }


def sample():
    rows = [row("{:06d}".format(i + 1)) for i in range(100)]
    return {
        "date": "2026-11-18",
        "editions": {
            "15:40": {
                "date": "2026-11-18",
                "rateBasis": "KRX_PREVIOUS_CLOSE",
                "stocks": copy.deepcopy(rows),
            },
            "20:10": {
                "date": "2026-11-18",
                "rateBasis": "KRX_PREVIOUS_CLOSE",
                "stocks": copy.deepcopy(rows),
            },
        },
    }


class FeaturedCloseTest(unittest.TestCase):
    def test_consistent_prices(self):
        self.assertEqual(validate(sample()), [])

    def test_after_hours_price_must_not_replace_regular_close(self):
        data = sample()
        data["editions"]["20:10"]["stocks"][0]["price"] = 120
        data["editions"]["20:10"]["stocks"][0]["changeRate"] = 20
        self.assertTrue(any("price differs" in x for x in validate(data)))

    def test_previous_close_must_match(self):
        data = sample()
        data["editions"]["20:10"]["stocks"][1]["previousRegularClose"] = 90
        self.assertTrue(any("previousRegularClose differs" in x for x in validate(data)))

    def test_rate_formula(self):
        data = sample()
        data["editions"]["20:10"]["stocks"][2]["changeRate"] = 19
        self.assertTrue(any("changeRate differs" in x for x in validate(data)))

    def test_no_evening_edition_yet(self):
        data = sample()
        del data["editions"]["20:10"]
        self.assertEqual(validate(data), [])

    def test_no_close_baseline(self):
        data = sample()
        del data["editions"]["15:40"]
        self.assertTrue(any("baseline is absent" in x for x in validate(data)))


if __name__ == "__main__":
    unittest.main()
