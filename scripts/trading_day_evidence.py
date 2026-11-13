"""Actual same-day KRX trades: official KIND plus independent quote corroboration.

HTTP 200 and a date in the page header never suffice to certify a trading day.
This path is only available after an actual regular-session trade has occurred.
"""
import datetime as dt
import json
import re
from html.parser import HTMLParser

KST=dt.timezone(dt.timedelta(hours=9))
KIND_QUOTE='https://kind.krx.co.kr/common/stockprices.do?isurCd=00593&method=searchStockPricesMain'
NAVER_QUOTE='https://stock.naver.com/api/domestic/detail/005930/detail?codeType=KRX'


class QuoteRows(HTMLParser):
    def __init__(self):super().__init__();self.active=False;self.cells=[];self.rows=[];self.text=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='table':self.active='거래대금' in attrs.get('summary','') and '일자' in attrs.get('summary','')
        if self.active and tag=='tr':self.cells=[]
        if self.active and tag=='td':self.text=[]
    def handle_data(self,data):
        if self.text is not None:self.text.append(data)
    def handle_endtag(self,tag):
        if tag=='td' and self.text is not None:self.cells.append(''.join(self.text).strip());self.text=None
        if self.active and tag=='tr' and self.cells:self.rows.append(self.cells)
        if tag=='table':self.active=False


def evidence(url,body,date,checked):
    observed=None;volume=amount=0
    if url==KIND_QUOTE:
        parser=QuoteRows();parser.feed(body)
        if not parser.rows:return None
        row=parser.rows[0]
        if len(row)<6:return None
        try:
            observed=dt.datetime.strptime(row[0],'%Y-%m-%d %H:%M:%S').replace(tzinfo=KST)
            volume=int(row[4].replace(',',''));amount=int(row[5].replace(',',''))
        except ValueError:return None
    elif url==NAVER_QUOTE:
        q=json.loads(body)
        if q.get('itemcode')!='005930':return None
        observed=dt.datetime.strptime(q['tradeTime'],'%Y%m%d%H%M%S').replace(tzinfo=KST)
        volume=int(q['tradeVolume']);amount=int(q['tradeAmount'])
    else:return None
    if (observed.date()!=date or observed>checked or volume<=0 or amount<=0
            or not dt.time(9)<=observed.time().replace(tzinfo=None)<=dt.time(18)):
        return None
    return {'sourceUrl':url,'market':'KRX','code':'005930','date':date.isoformat(),
            'observedAt':observed.isoformat(),'checkedAt':checked.isoformat(),
            'tradeVolume':volume,'tradeAmount':amount,'kind':'actual_krx_trade'}


def corroborated(results):
    records=[r['marketTradeEvidence'] for rows in results.values() for r in rows if r.get('marketTradeEvidence')]
    urls={r['sourceUrl'] for r in records}
    if {KIND_QUOTE,NAVER_QUOTE}.issubset(urls):
        return {'verified':True,'method':'official_kind_trade_plus_independent_krx_quote',
                'calendarSourceUrl':KIND_QUOTE,'sources':records}
    return {'verified':False,'method':'actual_trade_evidence_incomplete','sources':records}
