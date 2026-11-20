"""Validate Market Flow market-status display blocks."""
import argparse, datetime as dt, json
from pathlib import Path
from zoneinfo import ZoneInfo

KST=ZoneInfo("Asia/Seoul")
KINDS={"metrics","bullets","text"}

def req(ok,msg):
    if not ok: raise ValueError(msg)

def stamp(v):
    req(isinstance(v,str),"timestamp required")
    x=dt.datetime.fromisoformat(v.replace("Z","+00:00"))
    req(x.tzinfo is not None,"timezone required")
    return x

def validate_display(d):
    req(isinstance(d,dict),"display object required")
    req(isinstance(d.get("headline"),str) and d["headline"].strip(),"display headline required")
    badges=d.get("badges",[])
    req(isinstance(badges,list) and len(badges)<=4 and all(isinstance(x,str) and x.strip() for x in badges),"display badges invalid")
    stamp(d.get("observedAt"))
    sections=d.get("sections")
    req(isinstance(sections,list) and len(sections)>=1,"display sections required")
    ids=set()
    for s in sections:
        req(isinstance(s,dict),"display section object required")
        req(isinstance(s.get("id"),str) and s["id"] and s["id"] not in ids,"display section id invalid")
        ids.add(s["id"])
        req(isinstance(s.get("title"),str) and s["title"].strip(),"display section title required")
        kind=s.get("kind"); req(kind in KINDS,"display section kind invalid")
        if kind=="metrics":
            items=s.get("items")
            req(isinstance(items,list) and items,"metrics items required")
            for item in items:
                req(isinstance(item,dict) and isinstance(item.get("label"),str) and item["label"].strip(),"metric label required")
                req(item.get("value") is None or isinstance(item.get("value"),(int,float,str)) and not isinstance(item.get("value"),bool),"metric value invalid")
                if item.get("changePct") is not None:
                    req(isinstance(item["changePct"],(int,float)) and not isinstance(item["changePct"],bool),"metric changePct invalid")
                if item.get("note") is not None:
                    req(isinstance(item["note"],str),"metric note invalid")
        elif kind=="bullets":
            items=s.get("items")
            req(isinstance(items,list) and items and all(isinstance(x,str) and x.strip() for x in items),"bullet items invalid")
        else:
            req(isinstance(s.get("text"),str) and s["text"].strip(),"text section invalid")
    return d

def validate_day(body):
    req(isinstance(body,dict) and body.get("schemaVersion")==1,"schemaVersion")
    req(isinstance(body.get("date"),str),"date required")
    req(isinstance(body.get("editions"),dict),"editions required")
    for slot,e in body["editions"].items():
        req(isinstance(e,dict),"edition object required")
        req(e.get("slot")==slot,"slot mismatch")
        validate_display(e.get("display"))
    return body

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("file")
    a=p.parse_args()
    body=json.loads(Path(a.file).read_text(encoding="utf-8"))
    validate_day(body)
    print("Market status display contract valid.")
