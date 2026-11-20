"""Read-only audit of session-aware KRX/NXT featured-stock price calculations.

Denominator: previous KRX regular close for every session.
Numerator: PRE=NXT trade, REGULAR=KRX trade/close, AFTER=KRX/NXT after trade.
This is post-publication detection, not a pre-commit gate or live quote verification.
Legacy editions before 2026-11-19 did not carry session-source metadata.
"""
import argparse
import json
import sys
from datetime import datetime, time, timezone, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

TOLERANCE = Decimal("0.000002")
KST = timezone(timedelta(hours=9))
SESSION = {"08:40": "PRE", "09:40": "REGULAR",
           "11:40": "REGULAR", "13:40": "REGULAR",
           "15:40": "REGULAR", "20:10": "AFTER"}
SESSION_METADATA_START = "2026-11-20"


def decimal(value):
    try:
        d = Decimal(str(value))
    except (TypeError, InvalidOperation):
        return None
    return d if d.is_finite() else None


def parse_instant(value):
    try:
        d = datetime.fromisoformat(value)
        return d.astimezone(KST) if d.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def validate(day):
    problems = []
    date = day.get("date")
    editions = day.get("editions", {})
    if not isinstance(editions, dict):
        return ["editions must be an object"]
    old = editions.get("15:40", {}).get("stocks", [])
    prior_regular = {s.get("code"): s for s in old if isinstance(s, dict)}
    for slot, edition in editions.items():
        if slot not in SESSION:
            problems.append("unknown session slot {}".format(slot))
            continue
        if not isinstance(edition, dict):
            problems.append("{} edition is not an object".format(slot))
            continue
        # Do not retroactively fail pre-migration editions that were already published
        # without session-source metadata. 20:10 AFTER is the new strict contract.
        require_metadata = (slot == "20:10" and isinstance(date, str) and date >= "2026-11-20") or ("priceSession" in edition)
        if edition.get("date") != date:
            problems.append("{} edition date differs".format(slot))
        if edition.get("rateBasis") != "KRX_PREVIOUS_CLOSE":
            problems.append("{} missing KRX previous-close denominator".format(slot))
        stocks = edition.get("stocks")
        if not isinstance(stocks, list) or len(stocks) != 100:
            problems.append("{} does not contain 100 ranked stocks".format(slot))
            continue
        if require_metadata and edition.get("priceSession") != SESSION[slot]:
            problems.append("{} priceSession is not {}".format(slot, SESSION[slot]))
        codes = [s.get("code") for s in stocks]
        if len(set(codes)) != 100:
            problems.append("{} duplicate stock code".format(slot))
        for row in stocks:
            code = row.get("code")
            eligible = (row.get("comparison") or {}).get("eligible")
            price = decimal(row.get("price"))
            prior = decimal(row.get("previousRegularClose"))
            rate = decimal(row.get("changeRate"))
            if eligible:
                if price is None or prior is None or prior <= 0 or rate is None:
                    problems.append("{} {} missing valid price/prior/rate".format(slot, code))
                elif abs((price / prior - 1) * 100 - rate) > TOLERANCE:
                    problems.append("{} {} changeRate formula differs".format(slot, code))
            if slot == "20:10" and code in prior_regular:
                before_prior = decimal(prior_regular[code].get("previousRegularClose"))
                if before_prior != prior:
                    problems.append("{} 15:40/20:10 previousRegularClose differs".format(code))
                # The actual prices may differ: AFTER is not REGULAR.
            if not (require_metadata and eligible):
                continue
            market = row.get("priceMarket")
            if slot == "08:40" and market != "NXT":
                problems.append("{} 08:40 price must be from NXT PRE".format(code))
            if slot in ("09:40", "11:40", "13:40", "15:40") and market != "KRX":
                problems.append("{} {} regular price must be KRX".format(slot, code))
            if slot == "20:10" and market not in ("KRX", "NXT"):
                problems.append("{} AFTER source market missing".format(code))
            observed = parse_instant(row.get("priceObservedAt"))
            if observed is None or observed.date().isoformat() != date:
                problems.append("{} {} priceObservedAt absent or wrong date".format(slot, code))
            elif slot == "08:40" and not (time(8, 0) <= observed.time() <= time(8, 40)):
                problems.append("{} PRE trade outside pre-publication window".format(code))
            elif slot == "20:10" and not (time(15, 40) <= observed.time() <= time(20, 0)):
                problems.append("{} AFTER trade outside after-market window".format(code))
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="featured-stocks.json")
    parser.add_argument("--day-dir", default="featured-stocks")
    args = parser.parse_args()
    root = json.loads(Path(args.root).read_text(encoding="utf-8"))
    date = root.get("date")
    if not isinstance(date, str) or len(date) != 10:
        raise SystemExit("root featured-stocks.json has no valid date")
    path = Path(args.day_dir) / (date + ".json")
    if not path.is_file():
        raise SystemExit("daily edition not found: " + str(path))
    day = json.loads(path.read_text(encoding="utf-8"))
    problems = validate(day)
    if problems:
        print("FAIL: {} session-price errors on {}".format(len(problems), date))
        for item in problems[:30]:
            print(" - " + item)
        if len(problems) > 30:
            print(" - ... {} more".format(len(problems) - 30))
        sys.exit(1)
    print("PASS: session-aware price calculations for {}".format(date))


if __name__ == "__main__":
    main()
