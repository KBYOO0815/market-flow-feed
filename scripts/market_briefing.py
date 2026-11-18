"""Minimal validator/merger for Market Flow briefing JSON.

This helper validates only the app-facing data contract. It does not decide how
news is searched, selected, ranked, verified, or how U.S. themes are discovered.
"""
import argparse
import copy
import datetime as dt
import json
import math
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SLOTS = ("06:40", "08:40", "12:40", "19:40")
KST = ZoneInfo("Asia/Seoul")

def require(ok, message):
    if not ok:
        raise ValueError(message)

def timestamp(value):
    require(isinstance(value, str), "timestamp string required")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "timezone required")
    return parsed

def https(url):
    try:
        u = urlsplit(url)
        return u.scheme == "https" and bool(u.hostname) and not u.username and not u.password
    except (TypeError, ValueError):
        return False

def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def validate_theme(theme):
    require(isinstance(theme, dict), "theme object required")
    require(isinstance(theme.get("theme"), str) and theme["theme"].strip(), "theme name required")
    require(isinstance(theme.get("reason"), str) and theme["reason"].strip(), "theme reason required")
    if theme.get("direction") is not None:
        require(theme["direction"] in ("up", "down"), "invalid theme direction")
    if theme.get("weightedChangePct") is not None:
        require(finite(theme["weightedChangePct"]), "invalid weightedChangePct")
    if theme.get("totalDollarVolume") is not None:
        require(finite(theme["totalDollarVolume"]) and theme["totalDollarVolume"] >= 0, "invalid totalDollarVolume")
    stocks = theme.get("stocks", [])
    require(isinstance(stocks, list) and len(stocks) <= 5, "theme stocks limit")
    for stock in stocks:
        require(isinstance(stock, dict) and isinstance(stock.get("ticker"), str) and stock["ticker"].strip(), "theme ticker required")
        for key in ("regularChangePct", "afterHoursChangePct"):
            if stock.get(key) is not None:
                require(finite(stock[key]), "invalid theme stock change")

def validate_session(session, date, trading):
    require(isinstance(session, dict), "session object required")
    require(session.get("slot") in SLOTS, "invalid slot")
    require(trading or session["slot"] in ("06:40", "19:40"), "closed-day slot")
    cutoff = timestamp(session.get("asOf"))
    require(cutoff.astimezone(KST).date() == dt.date.fromisoformat(date), "asOf date mismatch")
    require(cutoff <= dt.datetime.now(KST), "future asOf")

    ids = set()
    for region, field in (("foreign", "foreignNews"), ("domestic", "domesticNews")):
        items = session.get(field)
        require(isinstance(items, list) and len(items) <= 10, "news limit")
        for rank, item in enumerate(items, 1):
            require(isinstance(item, dict), "news object required")
            for key in ("id", "title", "summary", "sourceName", "category"):
                require(isinstance(item.get(key), str) and item[key].strip(), "news strings")
            require(item.get("region") == region, "news region")
            require(item.get("impactRank") == rank, "news rank")
            require(item["id"] not in ids, "duplicate news id")
            ids.add(item["id"])
            require(timestamp(item.get("publishedAt")) <= cutoff, "news after cutoff")
            require(https(item.get("sourceUrl")), "HTTPS source required")
            require(isinstance(item.get("relatedStocks"), list) and all(isinstance(x, str) for x in item["relatedStocks"]), "relatedStocks")

    themes = session.get("usThemes")
    require(isinstance(themes, list) and len(themes) <= 6, "theme limit")
    require(session["slot"] == "06:40" or not themes, "themes outside 06:40")
    for theme in themes:
        validate_theme(theme)

    if session.get("researchStatus") is not None:
        require(session["researchStatus"] in ("complete", "partial", "failed"), "invalid researchStatus")
    if session.get("usThemeStatus") is not None:
        require(session["usThemeStatus"] in ("verified_themes", "verified_no_theme", "insufficient_data", "not_applicable"), "invalid usThemeStatus")

def validate(body, today=None):
    today = today or dt.datetime.now(KST).date()
    require(isinstance(body, dict) and body.get("schemaVersion") == 1, "schemaVersion")
    timestamp(body.get("updatedAt"))
    require(isinstance(body.get("days"), list), "days required")

    seen_dates = set()
    for day in body["days"]:
        require(isinstance(day, dict), "day object required")
        date = dt.date.fromisoformat(day["date"])
        require(today - dt.timedelta(days=3) <= date <= today, "outside FIFO range")
        require(date not in seen_dates, "duplicate date")
        seen_dates.add(date)
        require(type(day.get("isKrxTradingDay")) is bool, "trading flag")
        require(isinstance(day.get("sessions"), list), "sessions required")
        seen_slots = set()
        for session in day["sessions"]:
            require(session.get("slot") not in seen_slots, "duplicate slot")
            seen_slots.add(session["slot"])
            validate_session(session, day["date"], day["isKrxTradingDay"])
    return body

def merge(current, draft, today=None):
    today = today or dt.datetime.now(KST).date()
    require(isinstance(draft, dict), "draft object required")
    require(isinstance(draft.get("date"), str), "draft date required")
    require(type(draft.get("isKrxTradingDay")) is bool, "draft trading flag required")
    validate_session(draft.get("session"), draft["date"], draft["isKrxTradingDay"])

    result = copy.deepcopy(current)
    result.pop("researchState", None)
    result["days"] = [
        d for d in result.get("days", [])
        if today - dt.timedelta(days=3) <= dt.date.fromisoformat(d["date"]) <= today
    ]

    day = next((d for d in result["days"] if d["date"] == draft["date"]), None)
    if day is None:
        day = {"date": draft["date"], "isKrxTradingDay": draft["isKrxTradingDay"], "sessions": []}
        result["days"].append(day)
    require(day["isKrxTradingDay"] == draft["isKrxTradingDay"], "trading flag conflict")

    session = copy.deepcopy(draft["session"])
    old = next((s for s in day["sessions"] if s["slot"] == session["slot"]), None)
    if old is not None:
        require(timestamp(old["asOf"]) <= timestamp(session["asOf"]), "stale replacement")
    day["sessions"] = [s for s in day["sessions"] if s["slot"] != session["slot"]] + [session]
    day["sessions"].sort(key=lambda s: s["slot"])
    result["days"].sort(key=lambda d: d["date"], reverse=True)
    result["updatedAt"] = dt.datetime.now(KST).isoformat()
    return validate(result, today)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["validate", "merge"])
    parser.add_argument("files", nargs="+")
    parser.add_argument("--today", type=dt.date.fromisoformat)
    args = parser.parse_args()

    with open(args.files[0], encoding="utf-8") as f:
        body = json.load(f)

    if args.mode == "validate":
        validate(body, args.today)
        print("Market briefing JSON contract valid.")
    else:
        require(len(args.files) == 3, "merge CURRENT DRAFT OUTPUT")
        with open(args.files[1], encoding="utf-8") as f:
            draft = json.load(f)
        result = merge(body, draft, args.today)
        with open(args.files[2], "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")
