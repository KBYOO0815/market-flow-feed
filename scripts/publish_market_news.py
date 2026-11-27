"""Publish Claude's dated Drive news files without changing the app contract."""
import argparse
import copy
import datetime as dt
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

KST = dt.timezone(dt.timedelta(hours=9))
FOLDER = "1YBXHGxCZut2F1qLAqF7ryebg8EDyoXrQ"
TEST_ID = "1lYqAij5KP1nxAvD5rJCXhgxwJsiFdKTE"
SLOTS = {"08:00": "07:50", "15:20": "15:10"}
LIVE_FROM = dt.date(2026, 11, 28)
FEED = Path("market-news.json")
FAIL = Path(".market-news-input-failed")
LIMIT = 1024 * 1024

def stamp(value):
    if not isinstance(value, str):
        raise ValueError("Invalid timestamp")
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("Timezone required")
    return t.astimezone(KST)

def at(day, slot):
    return dt.datetime.fromisoformat(f"{day}T{slot}:00+09:00")

def filename(day, slot):
    return f"market-news-{day}-{slot.replace(':', '')}.json"

def validate(data, day, slot, now, test=False):
    if not isinstance(data, dict) or data.get("date") != str(day) or data.get("slot") != slot:
        raise ValueError("Wrong date or slot")
    if not test and (data.get("testOnly") is not None or day < LIVE_FROM):
        raise ValueError("Test input excluded")
    if test and data.get("testOnly") is not True:
        raise ValueError("Expected test marker")
    observed = stamp(data.get("asOf"))
    if observed.date() != day or observed > now:
        raise ValueError("Invalid observation date")
    if not test and observed < at(day, SLOTS[slot]):
        raise ValueError("Stale observation")
    ids = set()
    facts = set()
    for region in ("foreign", "domestic"):
        items = data.get(region + "News")
        if not isinstance(items, list) or len(items) > 10:
            raise ValueError("Invalid news array")
        for i, item in enumerate(items, 1):
            if not isinstance(item, dict):
                raise ValueError("Invalid news item")
            for key in ("id", "title", "summary", "sourceName", "sourceUrl", "category", "eventKey", "factKey"):
                if not isinstance(item.get(key), str) or not item[key].strip():
                    raise ValueError("Missing news field: " + key)
            u = urlsplit(item["sourceUrl"])
            if u.scheme != "https" or not u.hostname or u.username or u.password:
                raise ValueError("Invalid source URL")
            published, checked = stamp(item.get("publishedAt")), stamp(item.get("checkedAt"))
            if published > checked or checked > now:
                raise ValueError("Invalid source times")
            if item.get("region") != region or type(item.get("impactRank")) is not int or item["impactRank"] != i:
                raise ValueError("Invalid region or impact rank")
            stocks = item.get("relatedStocks")
            if not isinstance(stocks, list) or not all(isinstance(s, str) for s in stocks):
                raise ValueError("Invalid related stocks")
            fact = (item["eventKey"], item["factKey"])
            if item["id"] in ids or fact in facts:
                raise ValueError("Duplicate news")
            ids.add(item["id"])
            facts.add(fact)
    return {"slot": slot, "asOf": observed.isoformat(), "publishedAt": now.isoformat(timespec="seconds"),
            "foreignNews": copy.deepcopy(data["foreignNews"]), "domesticNews": copy.deepcopy(data["domesticNews"]),
            "usThemes": [], "researchStatus": "complete"}

def session_for(feed, day, slot):
    return next((s for d in feed["days"] if d["date"] == str(day) for s in d["sessions"] if s["slot"] == slot), None)

def merge(feed, day, slot, now, edition=None, failure=None):
    out = copy.deepcopy(feed)
    yesterday = day - dt.timedelta(days=1)
    out["days"] = [d for d in out["days"] if d["date"] in (str(yesterday), str(day))]
    if edition is not None and not session_for(out, day, slot):
        d = next((d for d in out["days"] if d["date"] == str(day)), None)
        if d is None:
            d = {"date": str(day), "displaySlots": list(SLOTS), "sessions": []}
            out["days"].append(d)
        d["displaySlots"] = list(SLOTS)
        d["sessions"].append(edition)
        d["sessions"].sort(key=lambda s: s["slot"])
    out["days"].sort(key=lambda d: d["date"])
    old_nav = {(n["date"], n["slot"]): n for group in feed["navigation"].values() for n in group}
    def nav(d):
        slots = list(SLOTS) if d >= LIVE_FROM else sorted(s["slot"] for x in out["days"] if x["date"] == str(d) for s in x["sessions"])
        rows = []
        for sl in slots:
            row = {"date": str(d), "slot": sl}
            if session_for(out, d, sl):
                row["state"] = "published"
            elif at(d, sl) > now:
                row["state"] = "scheduled"
            elif d == day and sl == slot and failure:
                row.update(state="failed", reason=failure)
            else:
                prev = old_nav.get((str(d), sl), {})
                row.update(state="failed" if prev.get("state") == "failed" else "missing")
                if row["state"] == "failed" and prev.get("reason"):
                    row["reason"] = prev["reason"]
            rows.append(row)
        return rows
    out["navigation"] = {"previous": nav(yesterday), "today": nav(day), "next": []}
    if out != feed:
        out["updatedAt"] = now.isoformat(timespec="seconds")
    return out

def drive_session():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    secret = os.environ.get("NEWS_DRIVE_SERVICE_ACCOUNT_JSON")
    if not secret:
        raise RuntimeError("NEWS_DRIVE_SERVICE_ACCOUNT_JSON not configured")
    credentials = service_account.Credentials.from_service_account_info(
        json.loads(secret), scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return AuthorizedSession(credentials)

def download(session, file_id):
    with session.get(f"https://www.googleapis.com/drive/v3/files/{file_id}", params={"alt": "media"}, timeout=30, stream=True) as r:
        r.raise_for_status()
        buf = bytearray()
        for chunk in r.iter_content(65536):
            buf.extend(chunk)
            if len(buf) > LIMIT:
                raise ValueError("Input exceeds 1 MiB")
    return json.loads(buf.decode("utf-8-sig"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Invalid JSON constant")))

def find_file(session, day, slot):
    name = filename(day, slot)
    query = f"'{FOLDER}' in parents and trashed = false and name = '{name}'"
    r = session.get("https://www.googleapis.com/drive/v3/files", params={
        "q": query, "fields": "files(id,name,createdTime),nextPageToken", "orderBy": "createdTime desc", "pageSize": 100}, timeout=30)
    r.raise_for_status()
    files = r.json().get("files", [])
    if not files:
        raise FileNotFoundError("Current Drive edition missing")
    return files[0]["id"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=list(SLOTS), default="08:00")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    now = dt.datetime.now(KST)
    day = now.date()
    if args.check:
        with drive_session() as session:
            data = download(session, TEST_ID)
        validate(data, dt.date(2026, 11, 27), "15:20", now, test=True)
        print("Drive test input verified; no publication")
        return
    if day < LIVE_FROM or now < at(day, args.slot):
        print("Outside eligible publication date/time")
        return
    # Do not let a delayed morning job publish after the afternoon collection starts.
    if args.slot == "08:00" and now >= at(day, "15:10"):
        print("Morning release window ended")
        return
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    if session_for(feed, day, args.slot):
        print("Already published; no change")
        return
    edition = None
    failure = None
    try:
        with drive_session() as session:
            data = download(session, find_file(session, day, args.slot))
        edition = validate(data, day, args.slot, dt.datetime.now(KST))
    except Exception as exc:
        # Do not log credentials, URLs with tokens, or private input.
        failure = "Drive 뉴스 입력 조회 또는 검증 실패 (" + type(exc).__name__ + ")"
        print(failure)
        FAIL.touch()
    result = merge(feed, day, args.slot, dt.datetime.now(KST), edition, failure)
    if result != feed:
        FEED.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if edition is not None:
        print(f"Prepared {day} {args.slot}: {len(edition['foreignNews'])} foreign, {len(edition['domesticNews'])} domestic")

if __name__ == "__main__":
    main()
