"""Read-only production-source diagnostics, distinct from a publishable Top100."""
import datetime as dt
import json
import pathlib
import urllib.request
from source_http import read
from trading_day_evidence import KIND_QUOTE,NAVER_QUOTE,evidence,corroborated
from featured_v3 import KST


def trading_probe():
    checked=dt.datetime.now(KST);records={};errors={};raw={}
    for url in (KIND_QUOTE,NAVER_QUOTE):
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'MarketFlow/1.0'})
            body=read(request).decode('utf-8',errors='replace');raw[url]=body
            row=evidence(url,body,checked.date(),dt.datetime.now(KST))
            records[url]=[{'marketTradeEvidence':row}]
        except Exception as error:errors[url]=type(error).__name__+': '+str(error)
    proof=corroborated(records)
    path=pathlib.Path('collection-artifacts/trading-day-probe.json');path.parent.mkdir(exist_ok=True)
    result={'checkedAt':dt.datetime.now(KST).isoformat(),'proof':proof,'errors':errors,'rawResponses':raw,
            'scope':'trading_day_only_not_top100','publishable':False}
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return {k:v for k,v in result.items() if k!='rawResponses'}
