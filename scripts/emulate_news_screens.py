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
    adb('shell', 'input', 'swipe', '540', '1900', '540', '800', '600')
    time.sleep(2)
print('\n'.join(seen))
(out / 'texts.txt').write_text('\n'.join(seen), encoding='utf-8')
assert any('자기주식' in t for t in seen), 'test feed items are not on screen'
