# -*- coding: utf-8 -*-
"""П3 год-пакет: сканер голов для целей year_empty (не-страи) + year_candidates + спец.
Запуск из КОРНЯ: python3 work/p3_scan.py <v1> [v2 ...] [--cat N] [--ctx K]
Печатает СЫРЫЕ строки головы (год читать из сырых — norm цифры уничтожает)."""
import json, sys, re
sys.path.insert(0, 'scripts')
from g_locate_cowork import norm as norm0

def norm(s):
    return norm0(s).replace('3', 'З')   # гомоглиф 3↔З (вето-13 §5.2, вето-14 §5.2)

args = sys.argv[1:]
only = None; ctx = 3
if '--cat' in args:
    i = args.index('--cat'); only = int(args[i+1]); del args[i:i+2]
if '--ctx' in args:
    i = args.index('--ctx'); ctx = int(args[i+1]); del args[i:i+2]
VOLS = set(args)

q = json.load(open('state/Ф5_очередь_docx.json', encoding='utf-8'))
# каталог нужен всегда (source кандидатов); файл каталога в state/ ровно один
import glob
cf = sorted(glob.glob('state/catalog_f5_*.json'))
assert len(cf) == 1, cf
cat = json.load(open(cf[0], encoding='utf-8'))
m = json.load(open('state/index_master_v18r.json', encoding='utf-8'))
xy = {r['cat_pos']: r.get('xlsx_year') for r in m['rows'] if r.get('cat_pos') is not None}

targets = []  # (vol_short, cat, kind, cur_year, hint, needle)
for e in q['year_empty']:
    if e.get('stray'): continue
    vs = e['vol'].split('_')[0]
    if vs in VOLS:
        targets.append((vs, e['cat'], 'empty', cat[e['cat']]['year'], xy.get(e['cat']), e['title']))
for e in q['year_candidates']:
    vs = cat[e['cat']]['source'].split('_')[0]
    if vs in VOLS:
        targets.append((vs, e['cat'], e['flag'], e['year_record'], xy.get(e['cat']), e['title']))
if 'v2' in VOLS:
    targets.append(('v2', 1186, 'спец 1929→1930 (вето-3 §4.1)', cat[1186]['year'], xy.get(1186), cat[1186]['title']))

try:
    OVR = json.load(open('work/p3_needles.json', encoding='utf-8'))
except FileNotFoundError:
    OVR = {}

lines_by_vol = {}
for vs in sorted({t[0] for t in targets}):
    lines_by_vol[vs] = json.load(open(f'work/{vs}_lines.json', encoding='utf-8'))
nl_by_vol = {vs: [norm(t) for _, t, _ in ls] for vs, ls in lines_by_vol.items()}

for vs, c, kind, cur, hint, title in sorted(targets, key=lambda t: (t[0], t[1])):
    if only and c != only: continue
    lines, nl = lines_by_vol[vs], nl_by_vol[vs]
    needle = OVR.get(str(c), title)
    # титул без альт-названий в скобках — надёжнее для голов
    base = re.sub(r'\s*[(«][^)»]*[)»]\s*$', '', needle) if str(c) not in OVR else needle
    nn = norm(base if len(base) >= 4 else needle)
    head, other, joins = [], [], []
    for i, s in enumerate(nl):
        off = s.find(nn)
        if off >= 0: (head if off <= 20 else other).append(i)
    for i in range(len(nl)-1):
        if nn in (nl[i]+nl[i+1]) and nn not in nl[i] and nn not in nl[i+1]:
            joins.append(i)
    print(f"\n== {vs} cat{c} [{kind}] cur={cur} xlsx={hint} «{title}» игла={base!r}: head={len(head)} other={len(other)} join={len(joins)}")
    show = head[:6] if head else (joins[:3] + other[:3])
    for i in show:
        for j in range(max(0, i-1), min(len(lines), i+ctx)):
            t = lines[j][1]
            if t: print(f"   @{j}: {t[:240]}")
        print("   ---")
