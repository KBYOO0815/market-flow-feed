"""Market Flow: copy Gemini content from Drive into the unified status feed."""
import argparse
import copy
import json
import math
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import exchange_calendars as xc

KST = ZoneInfo("Asia/Seoul")
SLOTS = {"us": "07:11", "kr": "15:41"}
US_ID = "1Wwtn3wBgHJAiz0Lih-P6ZC3DHu8GTpn0"
LIMIT = 1024 * 1024
TYPES = ["text", "metric", "list", "table", "link"]
FEED = Path("market-status.json")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def cell(value):
    return value is None or isinstance(value, str) or number(value)


def https_url(value):
    if not nonempty(value):
        return False
    p = urlparse(value)
    return p.scheme == "https" and bool(p.hostname) and not p.username and not p.password


def timestamp(value):
    require(nonempty(value), "missing timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(dt.tzinfo is not None, "timestamp must include timezone")
    return dt.astimezone(KST)


def market_day(day, region):
    return day - timedelta(days=1) if region == "us" else day


def session(day, region):
    market = market_day(day, region)
    cal = xc.get_calendar("XNYS" if region == "us" else "XKRX",
                          start=str(market - timedelta(days=14)),
                          end=str(market + timedelta(days=14)))
    if not cal.is_session(str(market)):
        return None
    return cal.session_close(str(market)).to_pydatetime().astimezone(KST)


def validate(data):
    require(isinstance(data, dict), "input must be object")
    for key in ("date", "marketDate"):
        require(isinstance(data.get(key), str) and date.fromisoformat(data[key]).isoformat() == data[key],
                "invalid " + key)
    require(data.get("slot") in SLOTS.values(), "invalid slot")
    timestamp(data.get("asOf"))
    content = data.get("content")
    require(isinstance(content, list) and bool(content), "empty content")
    for item in content:
        require(isinstance(item, dict) and item.get("type") in TYPES, "unsupported content item")
        kind = item["type"]
        require("title" not in item or nonempty(item["title"]), "invalid title")
        if kind == "text":
            require(nonempty(item.get("value")), "empty text")
        elif kind == "metric":
            require(nonempty(item.get("label")) and "value" in item and cell(item["value"]), "invalid metric")
            require(item.get("changePct") is None or number(item["changePct"]), "invalid changePct")
            require("note" not in item or isinstance(item["note"], str), "invalid note")
        elif kind == "list":
            require(isinstance(item.get("items"), list) and bool(item["items"]) and
                    all(nonempty(x) for x in item["items"]), "invalid list")
        elif kind == "table":
            cols, rows = item.get("columns"), item.get("rows")
            require(isinstance(cols, list) and bool(cols) and all(nonempty(x) for x in cols), "invalid columns")
            require(isinstance(rows, list) and bool(rows) and all(
                isinstance(r, list) and len(r) == len(cols) and all(cell(x) for x in r) for r in rows),
                "invalid table")
        else:
            require(nonempty(item.get("label")) and https_url(item.get("url")), "invalid link")
    return data


def eligible(data, region, now):
    validate(data)
    day = now.date()
    close = session(day, region)
    require(close is not None, "market closed: no new session")
    require(data["date"] == str(day) and data["slot"] == SLOTS[region], "stale or wrong edition")
    require(data["marketDate"] == str(market_day(day, region)), "stale or wrong marketDate")
    observed = timestamp(data["asOf"])
    require(close <= observed <= now, "observation must be after close and not in future")
    require(not any("테스트:" in str(x.get("title", "")) or "테스트용" in str(x.get("title", ""))
                    for x in data["content"]), "test payload cannot publish")
    require(now >= datetime.combine(day, time.fromisoformat(SLOTS[region]), KST), "before release slot")


def edition(data, now):
    # Legacy display is derived mechanically; content remains byte-for-byte equivalent as JSON data.
    sections, sources = [], []
    for i, item in enumerate(data["content"]):
        kind = item["type"]
        title = item.get("title", "")
        section = {"id": "content-" + str(i), "title": title}
        if kind == "text":
            section.update(kind="text", text=item["value"])
        elif kind == "metric":
            section.update(kind="metrics", items=[{k: item[k] for k in
                ("label", "value", "changePct", "note") if k in item}])
        elif kind == "list":
            section.update(kind="bullets", items=item["items"])
        elif kind == "table":
            section.update(kind="bullets", items=[" | ".join(
                f"{c}: {'미확인' if v is None else v}" for c, v in zip(item["columns"], row))
                for row in item["rows"]])
        else:
            sources.append({"name": item["label"], "url": item["url"], "checkedAt": ""})
            continue
        sections.append(section)
    return {"date": data["date"], "slot": data["slot"], "asOf": data["asOf"],
            "publishedAt": now.isoformat(timespec="seconds"), "content": copy.deepcopy(data["content"]),
            "display": {"headline": "미국 시황" if data["slot"] == SLOTS["us"] else "한국 시황",
                        "badges": [], "observedAt": data["asOf"], "sections": sections},
            "sources": sources}


def download(file_id):
    require(nonempty(file_id) and all(c.isalnum() or c in "-_" for c in file_id), "invalid Drive ID")
    url = "https://drive.google.com/uc?" + urlencode({"export": "download", "id": file_id})
    with urlopen(Request(url, headers={"User-Agent": "MarketFlow/1.0", "Accept": "application/json"}), timeout=30) as r:
        require(urlparse(r.geturl()).scheme == "https", "unexpected redirect")
        raw = r.read(LIMIT + 1)
    require(len(raw) <= LIMIT, "Drive input too large")
    return validate(json.loads(raw.decode("utf-8-sig"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x))))


def rebuild(feed, now, effective, region=None, state=None, reason=None):
    today = now.date()
    yesterday = today - timedelta(days=1)
    keep = {str(yesterday), str(today)}
    feed["days"] = sorted([d for d in feed["days"] if d["date"] in keep], key=lambda d: d["date"])
    existing = {d["date"]: d["editions"] for d in feed["days"]}
    oldnav = {(e["date"], e["slot"]): e for key in ("previous", "today")
              for e in feed["navigation"].get(key, [])}
    nav = {"previous": [], "today": [], "next": []}
    for key, day in (("previous", yesterday), ("today", today)):
        if day < effective:
            # Preserve actual historical editions in the retention window, not invented new slots.
            nav[key] = [{"date": str(day), "slot": s, "state": "published"}
                        for s in sorted(existing.get(str(day), {}))]
            continue
        for r, slot in SLOTS.items():
            entry = {"date": str(day), "slot": slot}
            if slot in existing.get(str(day), {}):
                entry["state"] = "published"
            elif session(day, r) is None:
                entry.update(state="skipped", reason="해당 시장 정규장 휴장")
            elif day == today and now < datetime.combine(day, time.fromisoformat(slot), KST):
                entry["state"] = "scheduled"
            elif day == today and r == region and state:
                entry.update(state=state, reason=reason)
            else:
                prior = oldnav.get((str(day), slot), {})
                if prior.get("state") in ("failed", "missing"):
                    entry.update({k: prior[k] for k in ("state", "reason", "errorCode") if k in prior})
                else:
                    entry.update(state="missing", reason="발행 데이터 없음")
            nav[key].append(entry)
    feed["navigation"] = nav


def process(feed, region, now, file_id, loader=download):
    effective = date.fromisoformat(feed["schedule"]["effectiveFrom"])
    require(now.date() >= effective, "schedule not active")
    slot = SLOTS[region]
    today = str(now.date())
    old = next((d for d in feed["days"] if d["date"] == today), None)
    state = reason = None
    if old and slot in old["editions"]:
        print("Already published; no duplicate")
    elif now < datetime.combine(now.date(), time.fromisoformat(slot), KST):
        print("Before release slot")
    elif session(now.date(), region) is None:
        print("Market closed; skip")
    elif not file_id:
        state, reason = "missing", "Google Drive 입력 파일 미연결"
        print(reason)
    else:
        try:
            data = loader(file_id)
            eligible(data, region, now)
            if old is None:
                old = {"date": today, "editions": {}}
                feed["days"].append(old)
            old["editions"][slot] = edition(data, now)
            print("Prepared edition:", today, slot)
        except Exception as exc:
            state, reason = "failed", "입력 조회 또는 검증 실패"
            print("Input rejected:", type(exc).__name__, str(exc)[:300])
    rebuild(feed, now, effective, region, state, reason)
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", choices=SLOTS, required=True)
    parser.add_argument("--check", action="store_true", help="download and validate only; never write")
    args = parser.parse_args()
    now = datetime.now(KST)
    file_id = US_ID if args.region == "us" else os.environ.get("MARKET_STATUS_KR_DRIVE_ID", "")
    if args.check:
        data = download(file_id)
        print("Drive download and schema OK:", data["date"], data["slot"], len(data["content"]), "items")
        # Exercise legacy conversion without writing anything.
        result = edition(data, now)
        require(result["content"] == data["content"], "content changed")
        try:
            eligible(data, args.region, now)
            print("Eligible for live publication")
        except ValueError as exc:
            print("Not eligible for live publication:", exc)
        return
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    original = copy.deepcopy(feed)
    state = process(feed, args.region, now, file_id)
    if feed != original:
        feed["updatedAt"] = datetime.now(KST).isoformat(timespec="seconds")
        FEED.write_text(json.dumps(feed, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if state == "failed":
        # Workflow commits the failure navigation state, then reports a failed run.
        Path(".market-status-input-failed").touch()


if __name__ == "__main__":
    main()
