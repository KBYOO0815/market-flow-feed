"""Cross-edition KRX regular-close consistency check for published featured stocks.

This is a deterministic, read-only *post-publication* quality check. It cannot
prove that either quote comes from an official KRX source, and does not block
ChatGPT's direct GitHub commit. The publisher must verify actual source data
before writing; the workflow flags conflicting published values afterward.
"""
import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

TOLERANCE = Decimal("0.000002")


def decimal(value):
    try:
        d = Decimal(str(value))
    except (TypeError, InvalidOperation):
        return None
    return d if d.is_finite() else None


def validate(day):
    problems = []
    date = day.get("date")
    editions = day.get("editions", {})
    if not isinstance(editions, dict):
        return ["editions must be an object"]
    after = editions.get("20:10")
    if after is None:
        return []  # No evening publication to compare yet.
    before = editions.get("15:40")
    if before is None:
        return ["20:10 edition exists but 15:40 KRX close baseline is absent"]
    if after.get("date") != date or before.get("date") != date:
        problems.append("edition and daily JSON dates disagree")
    for slot, edition in (("15:40", before), ("20:10", after)):
        if edition.get("rateBasis") != "KRX_PREVIOUS_CLOSE":
            problems.append(slot + " does not declare KRX_PREVIOUS_CLOSE rate basis")
        if not isinstance(edition.get("stocks"), list) or len(edition["stocks"]) != 100:
            problems.append(slot + " does not contain exactly 100 ranked stocks")
    old = {s.get("code"): s for s in before.get("stocks", [])}
    new = {s.get("code"): s for s in after.get("stocks", [])}
    overlap = old.keys() & new.keys()
    if not overlap:
        problems.append("15:40 and 20:10 have no overlapping stocks")
    for code in sorted(overlap):
        a, b = old[code], new[code]
        for field in ("price", "previousRegularClose"):
            if decimal(a.get(field)) != decimal(b.get(field)):
                problems.append(
                    "{} {} differs: 15:40={!r}, 20:10={!r}".format(
                        code, field, a.get(field), b.get(field)
                    )
                )
    for code, row in sorted(new.items()):
        if row.get("rateMarket") != "KRX":
            problems.append("{} 20:10 rateMarket is not KRX".format(code))
        price = decimal(row.get("price"))
        prior = decimal(row.get("previousRegularClose"))
        rate = decimal(row.get("changeRate"))
        eligible = (row.get("comparison") or {}).get("eligible")
        if eligible:
            if price is None or prior is None or prior <= 0 or rate is None:
                problems.append("{} 20:10 missing eligible price/prior/rate".format(code))
            elif abs((price / prior - 1) * 100 - rate) > TOLERANCE:
                problems.append("{} 20:10 changeRate differs from KRX-price formula".format(code))
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
        print("FAIL: {} KRX regular-close inconsistencies on {}".format(len(problems), date))
        for problem in problems[:30]:
            print(" - " + problem)
        if len(problems) > 30:
            print(" - ... {} more".format(len(problems) - 30))
        sys.exit(1)
    print("PASS: {} 15:40/20:10 KRX price consistency".format(date))


if __name__ == "__main__":
    main()
