"""Gemini free-form featured analysis -> app feed, with temporary 00.39 text adapter."""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit
import exchange_calendars as xc
from publish_market_news import KST, LIMIT, stamp, at, public_read, matching_ids, download

FOLDER = "14eWlknJsA0JvTGe7gwJ_GI0SVwrjnKsf"
TEST_DAY = dt.date(2026, 11, 27)
TEST_IDS = {"09:40": "1HtmN74L5qKOy4oG0enm8wrYgl-eZQj54", "14:50": "1NSq1khBGzVZ1F6-CV1JHW6kWgsha4nOv"}
SLOTS = {"09:40": "09:30", "14:50": "14:40"}
LIVE_FROM = dt.date(2026, 11, 30)
# Live publication explicitly enabled by owner; public-write input risk remains until sharing is restricted.
LIVE_ENABLED = True
FEED = Path("featured-stocks-unified.json")
FAIL = Path(".featured-input-failed")
NOTICE = "앱 표출 검증용 미검증 데이터입니다. 투자 판단에 사용하지 마십시오. 입력 관측 시각은 검증되지 않았습니다."
BASIS = "자유 검색 결과입니다. 상단의 기존 Top100·4%·가중 상승률 문구는 적용되지 않습니다."

def filename(day, slot):
    return f"featured-stocks-{day}-{slot.replace(':', '')}.json"

def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected nonempty text")
    return value

def array(value):
    if not isinstance(value, list):
        raise ValueError("Expected array")
    return value

def sources(value, test):
    urls = array(value)
    for url in urls:
        u = urlsplit(text(url))
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            raise ValueError("Invalid source URL")
    if not test and not urls:
        raise ValueError("Missing source URL")
    return urls

def stock(s):
    return {"name": text(s.get("name")), "changeRate": text(s.get("changeRate", s.get("change")))}

def normalize(d, day, slot, now, test=False):
    if not isinstance(d, dict) or d.get("date") != str(day) or d.get("slot") != slot:
        raise ValueError("Wrong date or slot")
    if not test and (day < LIVE_FROM or d.get("testOnly") is not None):
        raise ValueError("Test excluded")
    observed = stamp(d.get("asOf"))
    if observed.date() != day or observed > now or (not test and not at(day, SLOTS[slot]) <= observed <= at(day, slot)):
        raise ValueError("Invalid observation time")
    themes = []
    for t in array(d.get("themes")):
        items = [stock(s) for s in array(t.get("stocks"))]
        if not items:
            raise ValueError("Empty theme")
        themes.append({"name": text(t.get("name")), "reason": text(t.get("reason", t.get("catalyst"))),
                       "stocks": items, "sources": sources(t.get("sources"), test)})
    individuals = [{**stock(s), "reason": text(s.get("reason")), "sources": sources(s.get("sources"), test)}
                   for s in array(d.get("individualStocks"))]
    return {"marketSummary": text(d.get("marketSummary")), "themes": themes,
            "individualStocks": individuals, "outlook": text(d.get("outlook"))}

def edition(d, day, slot, now, test=False):
    a = normalize(d, day, slot, now, test)
    rows = []
    def row(id, name, summary, urls=()):
        reason = {"summary": summary, "causality": "source_attributed"}
        if urls:
            reason["sourceUrl"] = urls[0]
        rows.append({"id": id, "name": name, "stockCodes": [], "reason": reason})
    row("summary", "[테스트] 시장 핵심 요약" if test else "시장 핵심 요약",
        (NOTICE + "\n" if test else "") + BASIS + "\n\n" + a["marketSummary"])
    for i, t in enumerate(a["themes"], 1):
        row(f"theme-{i}", t["name"], t["reason"] + "\n\n" + "\n".join(s["name"] + "  " + s["changeRate"] for s in t["stocks"]), t["sources"])
    for i, s in enumerate(a["individualStocks"], 1):
        row(f"individual-{i}", "개별 특징주 · " + s["name"], s["changeRate"] + "\n" + s["reason"], s["sources"])
    row("outlook", "시장 핵심 관전 포인트", a["outlook"])
    out = {"schemaVersion": 3, "date": str(day), "slot": slot, "asOf": stamp(d["asOf"]).isoformat(),
           "publishedAt": now.isoformat(timespec="seconds"), "analysis": a,
           "stocks": [], "themes": rows, "individualStocks": []}
    if test:
        out["testOnly"] = True
    return out

def trading(day):
    return xc.get_calendar("XKRX").is_session(day.isoformat())

def get_edition(feed, day, slot):
    return feed["days"].get(str(day), {}).get("editions", {}).get(slot)

def merge(feed, day, slot, now, value=None, failure=None):
    out = copy.deepcopy(feed)
    prev = day - dt.timedelta(days=1)
    out["days"] = {k:v for k,v in out["days"].items() if k in (str(prev), str(day))}
    if value is not None and get_edition(out, day, slot) is None:
        out["days"].setdefault(str(day), {"date": str(day), "editions": {}})["editions"][slot] = value
    old = {(n["date"], n["slot"]): n for group in feed["navigation"].values() for n in group}
    def nav(d):
        slots = sorted(set(out["days"].get(str(d), {}).get("editions", {})) | (set(SLOTS) if d >= LIVE_FROM else set()))
        rows = []
        for sl in slots:
            e = get_edition(out, d, sl)
            r = {"date": str(d), "slot": sl}
            if e:
                r["state"] = "published"
                if e.get("testOnly"):
                    r["reason"] = "앱 표출 검증용 테스트 발행"
            elif not trading(d):
                r["state"] = "skipped"
                r["reason"] = "KRX 휴장일"
            elif at(d, sl) > now:
                r["state"] = "scheduled"
            elif d == day and sl == slot and failure:
                r.update(state="failed", reason=failure)
            else:
                previous = old.get((str(d), sl), {})
                r["state"] = "failed" if previous.get("state") == "failed" else "missing"
                if r["state"] == "failed" and previous.get("reason"):
                    r["reason"] = previous["reason"]
            rows.append(r)
        return rows
    out["navigation"] = {"previous": nav(prev), "today": nav(day), "next": []}
    if out != feed:
        out["updatedAt"] = now.isoformat(timespec="seconds")
    return out

def folder_ids(name):
    html = public_read(f"https://drive.google.com/embeddedfolderview?id={FOLDER}#list", 8 * LIMIT).decode("utf-8")
    ids = matching_ids(html, name)
    if not ids:
        raise FileNotFoundError("Current featured file not found")
    return ids

def load(day, slot, now):
    candidates = []
    for fid in folder_ids(filename(day, slot)):
        d = download(fid)
        if isinstance(d, dict) and d.get("testOnly") is True:
            continue
        candidates.append(edition(d, day, slot, now))
    if not candidates:
        raise ValueError("No eligible input")
    candidates.sort(key=lambda e: stamp(e["asOf"]), reverse=True)
    if len(candidates) > 1 and candidates[0]["asOf"] == candidates[1]["asOf"]:
        raise ValueError("Ambiguous duplicate observation")
    return candidates[0]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--slot", choices=list(SLOTS), default="09:40")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    now = dt.datetime.now(KST)
    if args.check:
        for slot, fid in TEST_IDS.items():
            if fid not in folder_ids(filename(TEST_DAY, slot)):
                raise ValueError("Known test file not found")
            e = edition(download(fid), TEST_DAY, slot, now, test=True)
            print(f"Drive test {slot}: {len(e['analysis']['themes'])} themes, {len(e['analysis']['individualStocks'])} individual; no publication")
        return
    if not LIVE_ENABLED:
        print("Live featured publication disabled pending read-only folder verification")
        return
    day = now.date()
    if day < LIVE_FROM or now < at(day, args.slot):
        print("Outside eligible publication window")
        return
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    if get_edition(feed, day, args.slot):
        print("Already published")
        return
    value = failure = None
    if trading(day):
        try:
            value = load(day, args.slot, dt.datetime.now(KST))
        except Exception as exc:
            failure = "Drive 특징주 입력 조회 또는 검증 실패 (" + type(exc).__name__ + ")"
            FAIL.touch()
            print(failure)
    out = merge(feed, day, args.slot, dt.datetime.now(KST), value, failure)
    if out != feed:
        FEED.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
