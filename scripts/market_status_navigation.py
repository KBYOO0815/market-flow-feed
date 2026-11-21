"""Validate Market Flow market-status navigation contract."""
import argparse, json, re
from pathlib import Path

STATES={"published","scheduled","skipped","missing","failed"}
GROUPS=("previous","today","next")

def req(ok,msg):
    if not ok: raise ValueError(msg)

def entry(x):
    req(isinstance(x,dict),"navigation entry object required")
    req(isinstance(x.get("date"),str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}",x["date"]),"navigation date")
    req(isinstance(x.get("slot"),str) and re.fullmatch(r"\d{2}:\d{2}",x["slot"]),"navigation slot")
    req(x.get("state") in STATES,"navigation state")
    if x.get("reason") is not None: req(isinstance(x["reason"],str) and x["reason"].strip(),"navigation reason")
    if x.get("errorCode") is not None: req(isinstance(x["errorCode"],str) and x["errorCode"].strip(),"navigation errorCode")
    return x

def validate(body):
    req(isinstance(body,dict) and body.get("schemaVersion")==1,"schemaVersion")
    nav=body.get("navigation")
    req(isinstance(nav,dict),"navigation required")
    seen=set()
    flattened=[]
    for group in GROUPS:
        rows=nav.get(group)
        req(isinstance(rows,list),"navigation group required")
        for row in rows:
            entry(row)
            key=(row["date"],row["slot"])
            req(key not in seen,"duplicate navigation entry")
            seen.add(key); flattened.append(row)
    req(flattened,"navigation cannot be empty")
    keys=[(x["date"],x["slot"]) for x in flattened]
    req(keys==sorted(keys),"navigation must be chronological across previous/today/next")
    published={(d.get("date"),slot) for d in body.get("dates",[]) if isinstance(d,dict)
               for slot in []}
    return body

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("file")
    a=p.parse_args()
    body=json.loads(Path(a.file).read_text(encoding="utf-8"))
    validate(body)
    print("Market status navigation contract valid.")
