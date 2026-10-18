# -*- coding: utf-8 -*-
"""Сканер голов: для каждой активной позиции тома ищет иглу (нормализованно),
приоритет хитам с совпадением в начале строки (голова). Компактный вывод.
Запуск: python3 work/g_scan.py <vol_label> <lines.json> [cat...]"""
import json, sys, re
sys.path.insert(0, 'scripts')
from g_locate_cowork import norm

vol, lf = sys.argv[1], sys.argv[2]
only = set(map(int, sys.argv[3:])) if len(sys.argv) > 3 else None
lines = json.load(open(lf, encoding='utf-8'))
q = json.load(open('state/Ф5_очередь_docx.json', encoding='utf-8'))
# needle overrides
try:
    OVR = json.load(open(f'work/{vol}_needles.json', encoding='utf-8'))
except FileNotFoundError:
    OVR = {}
nl = [norm(t) for _, t, _ in lines]
pos = [p for p in q['genre'] if p['vol'].startswith(vol) and not p.get('note')]
for p in pos:
    c = p['cat']
    if only and c not in only: continue
    needle = OVR.get(str(c), p['title'])
    nn = norm(needle)
    head_hits, other = [], []
    for i, s in enumerate(nl):
        off = s.find(nn)
        if off >= 0:
            (head_hits if off <= 20 else other).append(i)
    # склейки соседних строк
    joins = []
    for i in range(len(nl)-1):
        if nn in (nl[i]+nl[i+1]) and nn not in nl[i] and nn not in nl[i+1]:
            joins.append(i)
    print(f"\n== cat{c} «{p['title']}» игла={needle!r}: head={len(head_hits)} other={len(other)} join={len(joins)}")
    for i in head_hits[:6]:
        for j in range(i, min(len(lines), i+3)):
            t = lines[j][1]
            if t: print(f"   @{j}: {t[:230]}")
        print("   ---")
    if not head_hits:
        for i in (joins[:3] + other[:3]):
            for j in range(max(0,i-1), min(len(lines), i+3)):
                t = lines[j][1]
                if t: print(f"   ~@{j}: {t[:230]}")
            print("   ---")
