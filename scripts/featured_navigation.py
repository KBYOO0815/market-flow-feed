"""Validate featured-stocks index navigation."""
import json, re
from pathlib import Path

STATES={"published","scheduled","skipped","missing","failed"}
SLOTS=("08:40","09:40","11:40","13:40","15:40","20:10")

def req(ok,msg):
    if not ok: raise ValueError(msg)

def validate(body):
    req(isinstance(body,dict) and body.get("schemaVersion")==3,"schemaVersion")
    nav=body.get("navigation")
    req(isinstance(nav,dict),"navigation required")
    seen=set(); ordered=[]
    for group in ("previous","today","next"):
        rows=nav.get(group)
        req(isinstance(rows,list),"navigation group required")
        for row in rows:
            req(isinstance(row,dict),"entry required")
            req(isinstance(row.get("date"),str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}",row["date"]),"date")
            req(row.get("slot") in SLOTS,"slot")
            req(row.get("state") in STATES,"state")
            if row.get("reason") is not None:
                req(isinstance(row["reason"],str) and row["reason"].strip(),"reason")
            if row.get("errorCode") is not None:
                req(isinstance(row["errorCode"],str) and row["errorCode"].strip(),"errorCode")
            key=(row["date"],row["slot"])
            req(key not in seen,"duplicate")
            seen.add(key); ordered.append(key)
    req(ordered==sorted(ordered),"chronology")
    return body

if __name__=="__main__":
    body=json.loads(Path("featured-stocks/index.json").read_text(encoding="utf-8"))
    validate(body)
    print("Featured navigation contract valid.")
