"""Minimal validator/merger for Market Flow briefing JSON.

Validates only the app-facing contract. Search, editorial judgment and market
analysis remain the scheduled task's responsibility.
"""
import argparse, copy, datetime as dt, json, math
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SLOTS = ("06:40", "07:40", "08:40", "09:40", "10:40", "11:40", "12:40", "13:40", "14:40", "15:40", "16:40", "17:40", "18:40", "19:40", "22:40")
KST = ZoneInfo("Asia/Seoul")

def require(ok, message):
    if not ok: raise ValueError(message)

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

def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

def validate_theme(theme):
    require(isinstance(theme, dict), "theme object required")
    require(isinstance(theme.get("theme"), str) and theme["theme"].strip(), "theme name required")
    require(isinstance(theme.get("reason"), str) and theme["reason"].strip(), "theme reason required")
    if theme.get("direction") is not None:
        require(theme["direction"] in ("up", "down"), "invalid theme direction")
    for key in ("weightedChangePct", "totalDollarVolume"):
        if theme.get(key) is not None: require(finite(theme[key]), "invalid theme numeric")
    stocks = theme.get("stocks", [])
    require(isinstance(stocks, list) and len(stocks) <= 5, "theme stocks limit")

def validate_market_close(value):
    require(isinstance(value, dict), "marketClose object required")
    require(isinstance(value.get("summary"), str) and value["summary"].strip(), "marketClose summary required")
    for name in ("kospi", "kosdaq"):
        index = value.get(name)
        require(isinstance(index, dict), f"{name} required")
        require(finite(index.get("close")) and finite(index.get("changePct")), f"{name} close/change required")
    for key in ("leadingThemes", "weakThemes"):
        require(isinstance(value.get(key, []), list) and all(isinstance(x, str) for x in value.get(key, [])), f"{key} invalid")
    sources = value.get("sources")
    require(isinstance(sources, list) and len(sources) >= 1, "marketClose source required")
    for source in sources:
        require(isinstance(source, dict) and isinstance(source.get("name"), str) and source["name"].strip() and https(source.get("url")), "marketClose source invalid")

def validate_session(session, date, trading):
    require(isinstance(session, dict), "session object required")
    require(session.get("slot") in SLOTS, "invalid slot")
    require(trading or session["slot"] in ("06:40", "22:40"), "closed-day slot")
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
            require(item.get("region") == region and item.get("impactRank") == rank, "news region/rank")
            require(item["id"] not in ids, "duplicate news id"); ids.add(item["id"])
            require(timestamp(item.get("publishedAt")) <= cutoff, "news after cutoff")
            require(https(item.get("sourceUrl")), "HTTPS source required")
            require(isinstance(item.get("relatedStocks"), list) and all(isinstance(x, str) for x in item["relatedStocks"]), "relatedStocks")

    themes = session.get("usThemes")
    require(isinstance(themes, list) and len(themes) <= 6, "theme limit")
    require(session["slot"] == "06:40" or not themes, "themes outside 06:40")
    for theme in themes: validate_theme(theme)

    close = session.get("marketClose")
    # News editions are general-news sessions at every configured slot.
    # Keep legacy 15:40 marketClose readable when present, but never require it
    # and never force 15:40 news arrays to be empty. Market-status is the
    # authoritative market-close feed.
    if close is not None:
        require(session["slot"] == "15:40" and trading, "marketClose outside trading-day 15:40")
        validate_market_close(close)

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
        require(today - dt.timedelta(days=1) <= date <= today, "outside FIFO range")
        require(date not in seen_dates, "duplicate date"); seen_dates.add(date)
        require(type(day.get("isKrxTradingDay")) is bool, "trading flag")
        seen_slots = set()
        for session in day.get("sessions", []):
            require(session.get("slot") not in seen_slots, "duplicate slot"); seen_slots.add(session["slot"])
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
    result["days"] = [d for d in result.get("days", []) if today-dt.timedelta(days=1) <= dt.date.fromisoformat(d["date"]) <= today]
    day = next((d for d in result["days"] if d["date"] == draft["date"]), None)
    if day is None:
        day = {"date": draft["date"], "isKrxTradingDay": draft["isKrxTradingDay"], "sessions": []}
        result["days"].append(day)
    require(day["isKrxTradingDay"] == draft["isKrxTradingDay"], "trading flag conflict")
    session = copy.deepcopy(draft["session"])
    old = next((s for s in day["sessions"] if s["slot"] == session["slot"]), None)
    if old is not None: require(timestamp(old["asOf"]) <= timestamp(session["asOf"]), "stale replacement")
    day["sessions"] = [s for s in day["sessions"] if s["slot"] != session["slot"]] + [session]
    day["sessions"].sort(key=lambda s: SLOTS.index(s["slot"]))
    result["days"].sort(key=lambda d: d["date"], reverse=True)
    result["updatedAt"] = dt.datetime.now(KST).isoformat()
    return validate(result, today)

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["validate", "merge"])
    p.add_argument("files", nargs="+")
    p.add_argument("--today", type=dt.date.fromisoformat)
    a = p.parse_args()
    with open(a.files[0], encoding="utf-8") as f: body = json.load(f)
    if a.mode == "validate":
        validate(body, a.today); print("Market briefing JSON contract valid.")
    else:
        require(len(a.files) == 3, "merge CURRENT DRAFT OUTPUT")
        with open(a.files[1], encoding="utf-8") as f: draft = json.load(f)
        result = merge(body, draft, a.today)
        with open(a.files[2], "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2); f.write("\n")
