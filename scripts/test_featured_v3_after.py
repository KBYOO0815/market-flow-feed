"""Regression tests for 20:10 final after-market price selection."""
import unittest

from featured_v3 import KST, rank_universe, selected

DATE = "2026-11-20"
ASOF = "2026-11-20T20:10:00+09:00"
SOURCE = "https://example.com/quote"
MASTER_SOURCE = "https://example.com/master"
COVERAGE_SOURCE = "https://example.com/coverage"


def security(i):
    code = f"{i:06d}"
    return {
        "code": code,
        "name": "S" + code,
        "market": "KOSPI",
        "securityType": "COMMON",
        "classificationVerified": True,
        "classificationSourceUrl": MASTER_SOURCE,
    }


def krx_quote(i, session="REGULAR_CLOSE", price=101, observed="2026-11-20T15:30:00+09:00",
              final=False):
    code = f"{i:06d}"
    return {
        "code": code,
        "market": "KRX",
        "tradeDate": DATE,
        "turnoverScope": "KRX_ONLY",
        "sourceUrl": SOURCE + "/krx/" + code,
        "priceSourceUrl": SOURCE + "/krx/" + code,
        "retrievedAt": "2026-11-20T20:09:00+09:00",
        "observedAt": observed,
        "turnover": 2_000_000 - i * 1_000,
        "session": session,
        "closeConfirmed": session == "REGULAR_CLOSE",
        "finalConfirmed": final,
        "previousRegularClose": 100,
        "price": price,
        "comparison": {
            "eligible": True,
            "basis": "KRX_PREVIOUS_REGULAR_CLOSE",
            "explanation": "verified prior KRX regular close",
        },
    }


def nxt_quote(i, price=105, final=True):
    code = f"{i:06d}"
    return {
        "code": code,
        "market": "NXT",
        "tradeDate": DATE,
        "turnoverScope": "NXT_ONLY",
        "sourceUrl": SOURCE + "/nxt/" + code,
        "priceSourceUrl": SOURCE + "/nxt/" + code,
        "retrievedAt": "2026-11-20T20:09:00+09:00",
        "observedAt": "2026-11-20T19:59:00+09:00",
        "turnover": 100_000,
        "session": "NXT_FINAL",
        "closeConfirmed": False,
        "finalConfirmed": final,
        "price": price,
    }


def package(nxt_final=True):
    universe = [security(i) for i in range(100)]
    krx = [krx_quote(i) for i in range(100)]
    # Stock 0 has both KRX AFTER and NXT AFTER; NXT must win by fixed priority
    # even though the KRX after trade is later.
    krx[0] = krx_quote(
        0, session="KRX_AFTER_MARKET", price=107,
        observed="2026-11-20T19:59:30+09:00", final=True
    )
    # Stock 1 has only a KRX after-market trade.
    krx[1] = krx_quote(
        1, session="KRX_AFTER_MARKET", price=103,
        observed="2026-11-20T17:59:00+09:00", final=True
    )
    nxt = [nxt_quote(0, final=nxt_final)]
    coverage = {
        "date": DATE,
        "method": "full_universe",
        "securityMasterComplete": True,
        "krxComplete": True,
        "nxtComplete": True,
        "nxtEligibleCodes": ["000000"],
        "sourceUrl": COVERAGE_SOURCE,
    }
    return universe, krx, nxt, coverage


class FeaturedV3AfterMarketTest(unittest.TestCase):
    def test_2010_uses_latest_verified_after_market_price(self):
        universe, krx, nxt, coverage = package()
        rows, _ = rank_universe(
            universe, krx, nxt, coverage, DATE,
            __import__("featured_v3").stamp(ASOF), "20:10"
        )
        by = {row["code"]: row for row in rows}

        # Fixed priority chooses NXT AFTER over KRX AFTER, regardless of timestamp.
        self.assertEqual(by["000000"]["price"], 105)
        self.assertEqual(by["000000"]["priceMarket"], "NXT")
        self.assertEqual(by["000000"]["priceSession"], "AFTER")
        self.assertEqual(by["000000"]["changeRate"], 5.0)

        # With no verified NXT AFTER, KRX AFTER is the second priority.
        self.assertEqual(by["000001"]["price"], 103)
        self.assertEqual(by["000001"]["priceMarket"], "KRX")
        self.assertEqual(by["000001"]["changeRate"], 3.0)

        # With no NXT/KRX AFTER trade, fall back to the verified KRX regular close.
        self.assertEqual(by["000002"]["price"], 101)
        self.assertEqual(by["000002"]["priceMarket"], "KRX")
        self.assertEqual(by["000002"]["priceSession"], "REGULAR")
        self.assertEqual(by["000002"]["changeRate"], 1.0)
        self.assertTrue(by["000002"]["comparison"]["eligible"])

        self.assertEqual(selected(rows), ["000000"])

    def test_2010_unconfirmed_nxt_falls_back_to_krx_after(self):
        universe, krx, nxt, coverage = package(nxt_final=False)
        rows, _ = rank_universe(
            universe, krx, nxt, coverage, DATE,
            __import__("featured_v3").stamp(ASOF), "20:10"
        )
        by = {row["code"]: row for row in rows}
        self.assertEqual(by["000000"]["price"], 107)
        self.assertEqual(by["000000"]["priceMarket"], "KRX")
        self.assertEqual(by["000000"]["priceSession"], "AFTER")
        self.assertEqual(by["000000"]["changeRate"], 7.0)


if __name__ == "__main__":
    unittest.main()
