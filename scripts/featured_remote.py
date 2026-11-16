"""Featured-only GitHub reader: large full-universe evidence needs blob API."""
import base64
import json
import urllib.error
from publish_feed import api


def read_remote(path,ref='main',missing=False):
    try:
        obj=api('GET','contents/'+path+'?ref='+ref)
        if obj.get('encoding')!='base64' or not obj.get('content'):
            blob=api('GET','git/blobs/'+obj['sha'])
            return json.loads(base64.b64decode(blob['content'])),obj['sha']
        return json.loads(base64.b64decode(obj['content'])),obj['sha']
    except urllib.error.HTTPError as e:
        if e.code==404 and missing:return None,None
        raise
