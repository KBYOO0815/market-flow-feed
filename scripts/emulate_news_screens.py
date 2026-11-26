"""Opens the news tab, scrolls it, saves screenshots and the visible texts."""
import re, subprocess, time, xml.etree.ElementTree as ET
from pathlib import Path

out = Path('evidence')

def adb(*args):
    return subprocess.run(['adb', *args], capture_output=True, check=True).stdout

def snapshot(name):
    adb('shell', 'uiautomator', 'dump', '/sdcard/ui.xml')
    adb('pull', '/sdcard/ui.xml', str(out / (name + '.xml')))
    (out / (name + '.png')).write_bytes(adb('exec-out', 'screencap', '-p'))
    return list(ET.parse(out / (name + '.xml')).iter('node'))

def tap(node):
    x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
    adb('shell', 'input', 'tap', str((x1 + x2) // 2), str((y1 + y2) // 2))

nodes = snapshot('start')
for n in nodes:  # the emulator launcher sometimes shows its own "not responding" dialog
    if n.get('text') == 'Close app':
        tap(n)
        time.sleep(2)
        adb('shell', 'am', 'start', '-W', '-n', 'com.kbyoo0815.marketflow/.MainActivity')
        time.sleep(15)
        nodes = snapshot('start')
tap(next(n for n in nodes if n.get('text') == '뉴스'))
time.sleep(12)
seen = []
for i in range(8):
    new = [n.get('text') for n in snapshot(f'news-{i}') if n.get('text') and n.get('text') not in seen]
    if not new:
        break
    seen += new
    adb('shell', 'input', 'swipe', '540', '1700', '540', '900', '800')
    time.sleep(3)
    pid = subprocess.run(['adb', 'shell', 'pidof', 'com.kbyoo0815.marketflow'], capture_output=True).stdout.decode().strip()
    focus = [l.strip() for l in adb('shell', 'dumpsys', 'window').decode(errors='replace').splitlines() if 'mCurrentFocus' in l]
    print(f'DIAG after swipe {i}: pid={pid or "none"} {focus}')
print('\n'.join(seen))
print('DIAG crash buffer:')
print(adb('logcat', '-d', '-b', 'crash').decode(errors='replace')[-4000:])
print('DIAG app lines:')
log = adb('logcat', '-d').decode(errors='replace').splitlines()
print('\n'.join([l for l in log if re.search(r'FATAL|ANR in|ReactNativeJS|Force finishing|has died|lowmemorykiller.*marketflow', l)][-40:]))
(out / 'texts.txt').write_text('\n'.join(seen), encoding='utf-8')
assert any('자기주식' in t for t in seen), 'test feed items are not on screen'
