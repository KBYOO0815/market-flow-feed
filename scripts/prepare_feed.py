"""Validate a freshly reviewed briefing; publication must use one of eight KST slots."""
import datetime as dt
import json
import pathlib
import re
import sys
from urllib.parse import urlparse

KST = dt.timezone(dt.timedelta(hours=9))
SLOTS = (dt.time(6, 40), dt.time(7, 40), dt.time(8, 50), dt.time(11, 50), dt.time(14, 50), dt.time(15, 50), dt.time(18, 50), dt.time(20, 20))
CATEGORIES = {"미국증시", "반도체·AI", "정책·발언", "국내공시", "기타"}

def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone is required")
    return parsed

def https(value):
    u = urlparse(value if isinstance(value, str) else "")
    return u.scheme == "https" and bool(u.hostname) and not u.username and not u.password

def next_slot(release):
    local = release.astimezone(KST)
    for day in range(4):
        date = local.date() + dt.timedelta(days=day)
        if date.weekday() >= 5:
            continue
        for slot in SLOTS:
            candidate = dt.datetime.combine(date, slot, KST)
            if candidate > local:
                return candidate
    raise ValueError("next publication slot unavailable")

def validate(payload):
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 2:
        raise ValueError("fresh editorial schemaVersion 2 is required")
    as_of = timestamp(payload["asOf"])
    release = timestamp(payload["releaseAt"])
    local = release.astimezone(KST)
    if local.time().replace(tzinfo=None) not in SLOTS or local.weekday() >= 5:
        raise ValueError("releaseAt must be a weekday 06:40, 07:40, 08:50, 11:50, 14:50, 15:50, 18:50 or 20:20 KST slot")
    if payload.get("tradingDayVerified") is not True or not https(payload.get("calendarSourceUrl")):
        raise ValueError("verified KOSPI trading day evidence is required")
    if not release - dt.timedelta(minutes=20) <= as_of <= release + dt.timedelta(minutes=30):
        raise ValueError("asOf must be the actual fresh review time for this slot")
    items = payload.get("items")
    if not isinstance(items, list) or len(items) > 20:
        raise ValueError("items must be an array with at most 20 entries")
    # Starting with the next release, require a verifiable research coverage audit.
    # Counts alone do not prove research; source URLs and topic coverage are required.
    if local >= dt.datetime(2026, 11, 12, 11, 30, tzinfo=KST):
        audit = payload.get("researchAudit")
        if not isinstance(audit, dict):
            raise ValueError("researchAudit required: do not publish without source coverage")
        required = ("foreign_market", "foreign_policy", "foreign_technology",
                    "domestic_disclosures", "domestic_policy", "domestic_market")
        coverage = audit.get("coverage")
        if not isinstance(coverage, dict):
            raise ValueError("researchAudit.coverage required")
        for topic in required:
            record = coverage.get(topic)
            if not isinstance(record, dict) or not isinstance(record.get("checkedAt"), str):
                raise ValueError("missing research coverage: " + topic)
            checked = timestamp(record["checkedAt"])
            if not as_of - dt.timedelta(minutes=30) <= checked <= as_of:
                raise ValueError("stale research coverage: " + topic)
            urls = record.get("sourceUrls")
            if not isinstance(urls, list) or not urls or not all(https(url) for url in urls):
                raise ValueError("actual source URLs required: " + topic)
        for field in ("foreignCandidates", "domesticCandidates", "verifiedCandidates", "duplicateExcluded"):
            value = audit.get(field)
            if type(value) is not int or value < 0:
                raise ValueError("nonnegative measured researchAudit count required: " + field)
        if audit["verifiedCandidates"] < len(items) and payload.get("correction") is None:
            raise ValueError("verified candidate count below published item count")
    # Amendments retain the original cutoff and original audit. Post-publication
    # verification is recorded against the actual correction time, never backdated.
    correction = payload.get("correction")
    correction_added = set()
    corrected_at = None
    if correction is not None:
        if not isinstance(correction, dict) or correction.get("kind") != "post_publication_omission":
            raise ValueError("unknown correction type")
        corrected_at = timestamp(correction.get("correctedAt"))
        if corrected_at <= release or corrected_at <= as_of:
            raise ValueError("correction must occur after original publication")
        added = correction.get("addedItemIds")
        if not isinstance(added, list) or not added or not all(isinstance(x, str) for x in added) or len(set(added)) != len(added):
            raise ValueError("correction requires unique added item IDs")
        correction_added = set(added)
        if correction.get("newlyVerifiedCandidates") != len(added):
            raise ValueError("correction verified count must match added item count")
        if type(correction.get("originalItems")) is not int or correction["originalItems"] + len(added) != len(items):
            raise ValueError("correction original and added item counts differ")
        if audit["verifiedCandidates"] < correction["originalItems"]:
            raise ValueError("original research audit undercounts original items")
    ids, counts, domestic_started = set(), {"foreign": 0, "domestic": 0}, False
    for position, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError("item must be an object")
        for field in ("id", "title", "summary", "sourceName", "reviewNote"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError("missing " + field)
        if item["id"] in ids:
            raise ValueError("duplicate id")
        ids.add(item["id"])
        if not https(item.get("sourceUrl")) or not https(item.get("reviewSourceUrl")):
            raise ValueError("source and current-review HTTPS evidence are required")
        published, reviewed, expires = (timestamp(item[k]) for k in ("publishedAt", "reviewedAt", "validUntil"))
        original_review = as_of - dt.timedelta(minutes=15) <= reviewed <= as_of
        correction_review = (item["id"] in correction_added and
                             corrected_at - dt.timedelta(minutes=15) <= reviewed <= corrected_at)
        if published > release:
            raise ValueError("item was published after target releaseAt; use a later edition")
        if published > as_of or not (original_review or correction_review):
            raise ValueError("item publication/review time does not match original cutoff or correction")
        if not release < expires <= next_slot(release):
            raise ValueError("validUntil must expire no later than the next publication slot")
        region = item.get("region")
        if region not in counts:
            raise ValueError("explicit foreign/domestic region is required")
        counts[region] += 1
        if counts[region] > 10 or (region == "foreign" and domestic_started):
            raise ValueError("up to 10 foreign items must precede up to 10 domestic items")
        domestic_started |= region == "domestic"
        if item.get("category") not in CATEGORIES:
            raise ValueError("invalid category")
        if type(item.get("impactRank")) is not int or item["impactRank"] != position:
            raise ValueError("impactRank must be consecutive from 1")
        if not isinstance(item.get("relatedStocks"), list) or not all(isinstance(x, str) for x in item["relatedStocks"]):
            raise ValueError("invalid relatedStocks")
        if item.get("kind") not in {"news", "market_snapshot"}:
            raise ValueError("kind must distinguish news from intraday snapshots")
        intraday = re.search(r"장\s*초반|장중|현재\s*(?:거래|[0-9])", item["title"] + " " + item["summary"])
        if intraday and item["kind"] != "market_snapshot":
            raise ValueError("intraday market language requires a fresh market_snapshot")
        if item["kind"] == "market_snapshot":
            observed = timestamp(item["observedAt"])
            if not as_of - dt.timedelta(minutes=10) <= observed <= as_of:
                raise ValueError("intraday observation is stale")
            if expires > observed + dt.timedelta(minutes=15):
                raise ValueError("intraday quotes expire within 15 minutes of observation")
    if correction_added and not correction_added.issubset(ids):
        raise ValueError("correction references missing item IDs")
    return payload

def check_release(payload, now):
    release, as_of = timestamp(payload["releaseAt"]), timestamp(payload["asOf"])
    if now < release:
        raise ValueError("briefing cannot be published before its releaseAt")
    if now > release + dt.timedelta(minutes=30) or not dt.timedelta(0) <= now - as_of <= dt.timedelta(minutes=30):
        raise ValueError("publication or research is too late; re-research instead of relabelling old data")

def prepare(payload, now):
    validate(payload)
    check_release(payload, now)
    result = dict(payload)
    result["items"] = [dict(x) for x in payload["items"] if timestamp(x["validUntil"]) > now]
    for rank, item in enumerate(result["items"], 1):
        item["impactRank"] = rank
    return result

def main():
    args = sys.argv[1:]
    stage = bool(args and args[0] == "--stage")
    if stage:
        args = args[1:]
    if len(args) != 2:
        raise SystemExit("usage: prepare_feed.py [--stage] SOURCE DESTINATION")
    payload = json.loads(pathlib.Path(args[0]).read_text(encoding="utf-8"))
    result = validate(payload) if stage else prepare(payload, dt.datetime.now(KST))
    destination = pathlib.Path(args[1])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Validated", len(result["items"]), "items; releaseAt=", result["releaseAt"])

if __name__ == "__main__":
    main()

