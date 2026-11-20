"""Validate Market Flow per-run audit JSON (RUN_AUDIT_POLICY v1)."""
import argparse, datetime as dt, json, re
from zoneinfo import ZoneInfo
KST=ZoneInfo("Asia/Seoul")
STATUSES={"published","failed","skipped","partial"}
FEEDS={"news","featured-stocks","market-status"}
def require(ok,msg):
    if not ok: raise ValueError(msg)
def stamp(v):
    require(isinstance(v,str),"timestamp string required")
    x=dt.datetime.fromisoformat(v.replace("Z","+00:00"))
    require(x.tzinfo is not None,"timezone required")
    return x
def validate(a,today=None):
    today=today or dt.datetime.now(KST).date()
    require(isinstance(a,dict) and a.get("schemaVersion")==1,"schemaVersion")
    require(a.get("feed") in FEEDS,"feed")
    require(isinstance(a.get("date"),str),"date")
    date=dt.date.fromisoformat(a["date"])
    require(today-dt.timedelta(days=1)<=date<=today,"outside D/D-1")
    require(isinstance(a.get("slot"),str) and re.fullmatch(r"\d{2}:\d{2}",a["slot"]),"slot")
    start=stamp(a.get("startedAt"));finish=stamp(a.get("finishedAt"))
    require(start<=finish,"run chronology")
    require(a.get("status") in STATUSES,"status")
    require(isinstance(a.get("steps"),list),"steps")
    for step in a["steps"]:
        require(isinstance(step,dict) and isinstance(step.get("name"),str),"step")
        require(step.get("status") in {"success","failed","skipped","partial"},"step status")
        if step.get("startedAt") is not None and step.get("finishedAt") is not None:
            require(stamp(step["startedAt"])<=stamp(step["finishedAt"]),"step chronology")
    pub=a.get("publication")
    require(isinstance(pub,dict),"publication")
    require(type(pub.get("attempted")) is bool and type(pub.get("success")) is bool,"publication flags")
    require(type(pub.get("readbackVerified")) is bool,"readback flag")
    if a["status"]=="published":
        require(pub["success"] is True and pub["readbackVerified"] is True,"published requires commit/readback")
        require(isinstance(pub.get("commitSha"),str) and len(pub["commitSha"])>=7,"commit sha")
    if a["status"] in {"failed","partial"}:
        require(isinstance(a.get("failedStep"),str) and a["failedStep"],"failedStep required")
        require(isinstance(a.get("errorCode"),str) and a["errorCode"],"errorCode required")
        require(isinstance(a.get("errorMessage"),str) and a["errorMessage"],"errorMessage required")
    return a
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("file");p.add_argument("--today",type=dt.date.fromisoformat)
    a=p.parse_args()
    with open(a.file,encoding="utf-8") as f: body=json.load(f)
    validate(body,a.today)
    print("Run audit JSON contract valid.")
