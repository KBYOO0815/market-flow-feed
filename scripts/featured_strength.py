"""Evidence-gated breadth/money/catalyst ranking; percentages are percentage points.

Version 2 starts at 2026-11-13 15:40 KST. Version 3 starts at 20:10:
KRX top 100 and every eligible theme; the former cap is historical only. Thresholds
are operating defaults, not statistical estimates of investment returns.
"""
import datetime as dt
from featured_scope import amount, hundred_edition
from urllib.parse import urlparse

VERSION = 2
EFFECTIVE_AT = '2026-11-13T15:40:00+09:00'
NO_REASON = '명확한 당일 재료 확인 부족'
EVENTS = {'ordinary', 'preferred', 'ipo', 'tender_offer', 'control_dispute', 'other_event', 'unknown'}
ROLES = {'representative', 'components', 'equipment', 'materials', 'other', 'unknown'}
KINDS = {'industry', 'shared_material', 'individual_event', 'uncertain'}


def active(payload):
    return dt.datetime.fromisoformat(payload['releaseAt']) >= dt.datetime.fromisoformat(EFFECTIVE_AT)


def proof(item):
    u = urlparse(item.get('sourceUrl', ''))
    return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password and bool(item.get('fact', '').strip())


def review_fields(theme):
    basis = theme.get('groupingBasis', {})
    if basis.get('kind') not in KINDS or not proof(basis):
        raise ValueError('verified groupingBasis required (uncertain is allowed)')
    reason = theme.get('reason')
    if reason and reason.get('scope') not in {'industry', 'shared', 'company'}:
        raise ValueError('reason scope must distinguish industry/shared/company')
    if reason and reason['scope'] == 'company' and basis['kind'] != 'individual_event':
        raise ValueError('company catalyst cannot explain an industry theme')
    for e in theme.get('membershipEvidence', []):
        if e.get('eventType') not in EVENTS or e.get('valueChainRole') not in ROLES:
            raise ValueError('explicit eventType/valueChainRole required; unknown is allowed')
        if not proof(e):
            raise ValueError('member context requires source evidence')


def assess(theme, stocks, payload):
    review_fields(theme)
    members = [stocks[c] for c in theme['stockCodes']]
    evidence = {e['code']: e for e in theme['membershipEvidence']}
    up = [s for s in members if s['changeRate'] > 0]
    down = [s for s in members if s['changeRate'] < 0]
    n, u, d = len(members), len(up), len(down)
    total_money = sum(amount(s) for s in stocks.values())
    up_money = sum(amount(s) for s in up)
    share = up_money / total_money if total_money else 0
    money_top = set(payload['byTurnover'][:20])
    gain_top = set([c for c in payload['byChangeRate'] if stocks[c]['changeRate'] > 0][:20])
    both = sum(s['code'] in money_top & gain_top for s in up)
    ten = sum(s['changeRate'] >= 10 for s in up)
    twenty = sum(s['changeRate'] >= 20 or s.get('isUpperLimit') is True for s in up)
    # Market-cap and limit-up facts come only from the collected KRX observation.
    large = any(s.get('marketCapKrw', 0) >= 10_000_000_000_000 and evidence[s['code']]['valueChainRole'] == 'representative' for s in up)
    suppliers = any(0 < s.get('marketCapKrw', 0) < 10_000_000_000_000 and evidence[s['code']]['valueChainRole'] in {'components', 'equipment', 'materials'} for s in up)
    spread = large and suppliers
    reason = theme.get('reason')
    material = 10 if reason and reason['causality'] == 'source_attributed' else 3 if reason else 0
    components = {
        'breadth': round(35 * min(u / 5, 1) * (u / n), 6),
        'intensity': round(20 * (.5 * min(ten / 3, 1) + .3 * min(twenty / 2, 1) + .2 * min(sum(max(s['changeRate'], 0) for s in up) / max(u, 1) / 10, 1)), 6),
        'money': round(25 * (.7 * min(share / .20, 1) + .3 * min(both / 3, 1)), 6),
        'leader': 5 if any(s['code'] in money_top & gain_top and s['changeRate'] >= 5 for s in up) else 0,
        'largeSmallSpread': 5 if spread else 0,
        'material': material,
    }
    score = round(sum(components.values()), 6)
    kind = theme['groupingBasis']['kind']
    ordinary = all(evidence[s['code']]['eventType'] == 'ordinary' for s in members)
    eligible = (kind in {'industry', 'shared_material'} and ordinary and u >= 3 and u / n >= .6
                and d < n / 2 and theme['weightedChangeRate'] > 0 and share >= .01)
    if kind == 'uncertain' or any(evidence[s['code']]['eventType'] == 'unknown' for s in members):
        label = '확인 부족'
    elif not u:
        label = '약세' if d else '혼조'
    elif d >= n / 2:
        label = '약세' if d > n / 2 else '혼조'
    elif u <= 2 or kind == 'individual_event' or not ordinary:
        label = '개별 강세'
    elif not eligible:
        label = '선별 강세' if up_money and max(amount(s) for s in up) / up_money >= .7 else '부분 강세'
    elif score >= 85 and u >= 5 and ten >= 3 and both >= 3 and share >= .20:
        label = '압도적 주도'
    elif score >= 65 and both >= 2 and share >= .08:
        label = '주도'
    elif ten >= 2 and u >= 3:
        label = '강한 확산'
    else:
        label = '강세'
    return dict(theme, strength={
        'judgment': label, 'eligible': eligible, 'score': score, 'components': components,
        'risingCount': u, 'fallingCount': d, 'flatCount': n-u-d,
        'risingRatio': round(u/n, 6), 'atLeast10Count': ten, 'atLeast20OrLimitCount': twenty,
        'positiveTurnoverShare': round(share, 6), 'bothTop20Count': both,
        'largeSmallSpreadVerified': spread,
        'exclusionReasons': ([] if eligible else [
            reason for test, reason in [
                (kind not in {'industry', 'shared_material'}, '공통 산업·재료 확인 부족 또는 개별 이벤트'),
                (not ordinary, '우선주·신규상장·개별 이벤트 또는 유형 확인 부족'),
                (u < 3, '상승 종목 3개 미만'), (u/n < .6, '상승 종목 비중 60% 미만'),
                (d >= n/2, '하락 종목 비중 50% 이상'),
                (theme['weightedChangeRate'] <= 0, '거래대금 가중 등락률 양수 아님'),
                (share < .01, '입력 전체 대비 상승 종목 거래대금 1% 미만'),
            ] if test]),
    })


def conclusions(themes, stocks):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
    lines = ['| 순위 | 테마 | 판정 | 상승 재료 |', '| -- | --- | --- | --- |']
    for i, t in enumerate(themes, 1):
        names = ', '.join(stocks[c]['name'] + ' ' + format(stocks[c]['changeRate'], '+.2f') + '%' for c in t['stockCodes'])
        reason = t.get('reason')
        material = NO_REASON
        if reason:
            prefix = '' if reason['causality'] == 'source_attributed' else '관련 사실 확인·상승 인과 확인 부족: '
            material = prefix + reason['summary']
        lines.append('| ' + ' | '.join(map(cell, [i, t['name'], t['strength']['judgment'] + ' — ' + names, material])) + ' |')
    final = ' → '.join(str(i) + '위 ' + t['name'] for i,t in enumerate(themes, 1))
    lines += ['', '**최종: ' + (cell(final) + ' 순으로 강하다.' if themes else '선정 기준을 충족한 강한 테마 없음.') + '**']
    return '\n'.join(lines) + '\n'


def analyze(payload, themes):
    stocks = {s['code']: s for s in payload['stocks']}
    rows = [assess(t, stocks, payload) for t in themes]
    rows.sort(key=lambda t: (-t['strength']['score'], -amount(t), t['id']))
    selected = [t for t in rows if t['strength']['eligible']]
    if not hundred_edition(payload['releaseAt']):
        selected = selected[:3]  # Preserve pre-migration editions exactly.
    used = {c for t in selected for c in t['stockCodes']}
    return {'themeSelectionVersion': 3 if hundred_edition(payload['releaseAt']) else VERSION, 'themeAssessments': rows, 'themes': selected,
            'unclassified': [c for c in payload['byChangeRate'] if c not in used],
            'reportMarkdown': conclusions(selected, stocks)}


def verify_analysis(payload):
    # Recompute everything: saved judgment/score/report must never bypass source gates.
    expected = analyze(payload, payload['themeAssessments'])
    if any(payload.get(k) != v for k, v in expected.items()):
        raise ValueError('theme strength/selection/report mismatch')
