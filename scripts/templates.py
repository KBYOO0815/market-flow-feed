"""Sentences written by code from DART values. Returns (title, summary), or None to fall back to a link."""
import re
from dart_news_test import josa, won, day_kr

TREASURY_APIS = {
    '주요사항보고서(자기주식취득결정)': 'tsstkAqDecsn',
    '주요사항보고서(자기주식취득신탁계약체결결정)': 'tsstkAqTrctrCnsDecsn',
}
DIVIDEND_REPORT = '현금ㆍ현물배당결정'

def blank(v):
    return v is None or str(v).strip() in ('', '-')

def line(v):
    return str(v).strip().split('\n')[0].strip()

def kdate(v):
    m = re.fullmatch(r'\s*(\d{4})\D+(\d{1,2})\D+(\d{1,2})\D*', str(v))
    return f'{m[1]}년 {int(m[2])}월 {int(m[3])}일' if m else None

def amount(v):
    return None if blank(v) or not re.fullmatch(r'[\d,]+', str(v).strip()) else won(str(v).strip())

def caveat(text):
    """Keeps the filing's own warning that the bought amount or share count can change."""
    if not text:
        return ' 상세 조건은 DART 원문에서 확인해야 한다.'
    for s in re.split(r'(?<=다\.)', text):
        if '실제' in s and '수량' in s and ('변동' in s or '달라' in s):
            what = '취득금액과 수량' if '금액' in s[s.index('실제'):] else '취득 수량'
            return f' 주가 변동 등에 따라 실제 {josa(what, "은", "는")} 달라질 수 있다.'
    return ''

def treasury(company, api, row, text=None):
    subject = josa(company, '은', '는')
    if api == 'tsstkAqDecsn':
        if not blank(row.get('aqpln_stk_estk')) or not blank(row.get('aqpln_prc_estk')):
            return None  # other share classes: not covered by this sentence
        decided, begin, end = (kdate(row.get(k)) for k in ('aq_dd', 'aqexpd_bgd', 'aqexpd_edd'))
        shares, money = row.get('aqpln_stk_ostk'), amount(row.get('aqpln_prc_ostk'))
        if not (decided and begin and end and money) or blank(shares) or blank(row.get('aq_pp')) or blank(row.get('aq_mth')):
            return None
        return (f'{company}, {money} 자기주식 취득 결정',
                f"{subject} {decided} 보통주 {shares}주(취득예정금액 {money})를 취득하기로 결정했다. "
                f"취득예상기간은 {begin}부터 {end}까지다. 취득방법은 '{line(row['aq_mth'])}', 취득목적은 '{line(row['aq_pp'])}'이다." + caveat(text))
    decided, begin, end = (kdate(row.get(k)) for k in ('bddd', 'ctr_pd_bgd', 'ctr_pd_edd'))
    money = amount(row.get('ctr_prc'))
    if not (decided and begin and end and money) or blank(row.get('ctr_cns_int')) or blank(row.get('ctr_pp')):
        return None
    broker = line(row['ctr_cns_int']).replace('(주)', '').replace('주식회사', '').strip()
    return (f'{company}, {money} 자기주식 취득 신탁계약 결정',
            f"{subject} {decided} {josa(broker, '과', '와')} {money} 규모의 자기주식 취득 신탁계약을 체결하기로 결정했다. "
            f"계약기간은 {begin}부터 {end}까지다. 계약목적은 '{line(row['ctr_pp'])}'이다." + caveat(text))

def dividend(company, report, text):
    if report.replace(' ', '') != DIVIDEND_REPORT:
        return None  # corrections and subsidiary filings are shown as links
    def find(pattern):
        m = re.search(pattern, text)
        return m.group(1).strip() if m else None
    kind = find(r'1\. 배당구분 (\S+) 2\.')
    form = find(r'2\. 배당종류 (\S+) ')
    per = find(r'1주당 배당금 ?\(원\) 보통주식 ([\d,]+) ')
    other = find(r'1주당 배당금 ?\(원\) 보통주식 [\d,]+ 종류주식 (\S+) ')
    rate = find(r'시가배당[률율] ?\(%\) 보통주식 (\S+) ')
    total = amount(find(r'배당금총액 ?\(원\) ([\d,]+)'))
    record = find(r'6\. 배당기준일 (\d{4}-\d{2}-\d{2})')
    paid = find(r'배당금지급 ?예정일자 (\d{4}-\d{2}-\d{2})')
    decided = find(r'이사회결의일 ?\(결정일\) (\d{4}-\d{2}-\d{2})')
    meeting = find(r'주주총회 ?예정일자 (\d{4}-\d{2}-\d{2})')
    needs_vote = bool(re.search(r'승인기관 주주총회|주주총회 개최여부 개최', text))
    if form != '현금배당' or other != '-' or '차등배당 여부 미해당' not in text or not (kind and per and total and record and decided):
        return None
    lines = [f'{josa(company, "은", "는")} {day_kr(decided)} 보통주 1주당 {per}원의 {kind}(현금)을 결정했다.',
             f'배당금총액은 {total}' + (f', 시가배당률은 {rate}%' if rate and rate != '-' else '') + '다.',
             f'배당기준일은 {day_kr(record)}' + (f', 지급 예정일은 {day_kr(paid)}' if paid else '') + '이다.']
    if needs_vote:
        lines.append('주주총회 승인이 필요하다' + (f'(예정일 {day_kr(meeting)}).' if meeting else '.'))
    if re.search(r'변경될 수', text):
        lines.append('내용은 변경될 수 있다.')
    return f'{company}, 1주당 {per}원 {kind} 결정', ' '.join(lines)
