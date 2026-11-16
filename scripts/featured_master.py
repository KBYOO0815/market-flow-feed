"""Public KIS security-master diagnostics, TLS verified; no credential needed.

Layouts: koreainvestment/open-trading-api/stocks_info/kis_{kospi,kosdaq}_code_mst.py.
Classification mappings require separate verification before publishable use.
"""
import datetime as dt
import hashlib
import io
import json
import pathlib
import urllib.request
import zipfile
from collections import Counter
from source_http import read
from featured_v3 import KST, require

LAYOUTS={
 'KOSPI':([2,1,4,4,4,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,9,5,5,1,1,1,2,1,1,1,2,2,2,3,1,3,12,12,8,15,21,2,7,1,1,1,1,1,9,9,9,5,9,8,9,3,1,1,1],19,54),
 'KOSDAQ':([2,1,4,4,4,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,9,5,5,1,1,1,2,1,1,1,2,2,2,3,1,3,12,12,8,15,21,2,7,1,1,1,1,9,9,9,5,9,8,9,3,1,1,1],14,49)
}


def probe():
    results={};out=pathlib.Path('collection-artifacts');out.mkdir(exist_ok=True)
    for market,(widths,spac,pref) in LAYOUTS.items():
        basename='kospi' if market=='KOSPI' else 'kosdaq';url='https://new.real.download.dws.co.kr/common/master/'+basename+'_code.mst.zip'
        try:
            raw=read(urllib.request.Request(url,headers={'User-Agent':'MarketFlow/1.0'}));z=zipfile.ZipFile(io.BytesIO(raw));info=z.getinfo(basename+'_code.mst')
            lines=z.read(info).decode('cp949').splitlines();rows=[]
            for line in lines:
                require(len(line)>sum(widths)+21,'master layout length mismatch')
                part=line[-sum(widths):];prefix=line[:-sum(widths)];fields=[];offset=0
                for width in widths:fields.append(part[offset:offset+width].strip());offset+=width
                rows.append({'code':prefix[:9].strip(),'isin':prefix[9:21].strip(),'name':prefix[21:].strip(),'groupCode':fields[0],'spacFlag':fields[spac],'preferredCode':fields[pref]})
            require(len(rows)==len({r['code'] for r in rows}),'duplicate master code')
            body={'sourceUrl':url,'retrievedAt':dt.datetime.now(KST).isoformat(),'zipFileTimestamp':info.date_time,'sha256':hashlib.sha256(raw).hexdigest(),'rows':rows,'publishable':False}
            (out/(basename+'-master-probe.json')).write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
            results[market]={'rows':len(rows),'groups':dict(Counter(r['groupCode'] for r in rows)),'spacFlags':dict(Counter(r['spacFlag'] for r in rows)),'preferredCodes':dict(Counter(r['preferredCode'] for r in rows)),'sourceUrl':url,'publishable':False}
        except Exception as e:results[market]={'error':type(e).__name__+': '+str(e),'sourceUrl':url,'publishable':False}
    return results
