"""Validate Market Flow per-run audit JSON (RUN_AUDIT_POLICY v2)."""
import argparse, datetime as dt, json, re
from zoneinfo import ZoneInfo

KST=ZoneInfo("Asia/Seoul")
STATUSES={"running","published","failed","skipped","partial"}
STEP_STATUSES={"running","success","failed","skipped","partial"}
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
    require(isinstance(a,dict) and a.get("schemaVersion")==2,"schemaVersion")
    require(a.get("feed") in FEEDS,"feed")
    require(isinstance(a.get("date"),str),"date")
    date=dt.date.fromisoformat(a["date"])
    require(today-dt.timedelta(days=1)<=date<=today,"outside D/D-1")
    require(isinstance(a.get("slot"),str) and re.fullmatch(r"\d{2}:\d{2}",a["slot"]),"slot")
    scheduled=stamp(a.get("scheduledFor"))
    start=stamp(a.get("startedAt"))
    updated=stamp(a.get("updatedAt"))
    require(updated>=start,"updatedAt before startedAt")
    require(a.get("status") in STATUSES,"status")
    require(isinstance(a.get("phase"),str) and a["phase"],"phase")
    require(isinstance(a.get("lastCompletedStep"),str) and a["lastCompletedStep"],"lastCompletedStep")
    require(isinstance(a.get("nextStep"),str) or a.get("nextStep") is None,"nextStep")

    finish=a.get("finishedAt")
    if a["status"]=="running":
        require(finish is None,"running must not have finishedAt")
    else:
        finish=stamp(finish)
        require(start<=finish,"run chronology")
        require(updated<=finish or updated==finish,"updatedAt after finishedAt")

    require(isinstance(a.get("steps"),list) and a["steps"],"steps")
    for step in a["steps"]:
        require(isinstance(step,dict) and isinstance(step.get("name"),str) and step["name"],"step")
        require(step.get("status") in STEP_STATUSES,"step status")
        if step.get("startedAt") is not None: stamp(step["startedAt"])
        if step.get("finishedAt") is not None:
            require(step.get("startedAt") is not None,"finished step needs startedAt")
            require(stamp(step["startedAt"])<=stamp(step["finishedAt"]),"step chronology")

    pub=a.get("publication")
    require(isinstance(pub,dict),"publication")
    require(type(pub.get("attempted")) is bool and type(pub.get("success")) is bool,"publication flags")
    require(type(pub.get("readbackVerified")) is bool,"readback flag")

    if a["status"]=="published":
        require(pub["attempted"] and pub["success"] and pub["readbackVerified"],"published requires commit/readback")
        require(isinstance(pub.get("commitSha"),str) and len(pub["commitSha"])>=7,"commit sha")
        require(a.get("nextStep") is None,"published nextStep must be null")

    if a["status"] in {"failed","partial"}:
        require(isinstance(a.get("failedStep"),str) and a["failedStep"],"failedStep required")
        require(isinstance(a.get("errorCode"),str) and a["errorCode"],"errorCode required")
        require(isinstance(a.get("errorMessage"),str) and a["errorMessage"],"errorMessage required")

    return a

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--today",type=dt.date.fromisoformat)
    a=p.parse_args()
    with open(a.file,encoding="utf-8") as f: body=json.load(f)
    validate(body,a.today)
    print("Run audit JSON contract v2 valid.")
