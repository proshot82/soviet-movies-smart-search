# -*- coding: utf-8 -*-
"""k1: канон genre — Ералаш (56) + Фитиль v10 №176–187 (11). Верификация по головам томов."""
import json, re, os
cat = json.load(open('state/catalog_f5_s6.json', encoding='utf-8'))
al = json.load(open('state/alignment_v17.json', encoding='utf-8'))
S = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}
def norm(s):
    t = s.replace('Ns','№').replace('N°','№').replace('Na','№').replace('N ','№ ')
    return t.upper().replace('Ё','Е')
lines = {}
def L(v):
    if v not in lines:
        lines[v] = json.load(open(f'work/{v}_lines.json', encoding='utf-8'))
    return lines[v]
SET = {}
report = []
# ── Ералаш ──
CANON_E = 'Детский юмористический киножурнал'
for i, r in enumerate(cat):
    if i in S: continue
    m = re.match(r'^Ералаш № (\d+)$', r['title'])
    if not m: continue
    num = int(m.group(1)); v = r['source'].split('_')[0]
    # локализовать голову: строка с ЕРАЛАШ № num (первая половина тома, не указатель)
    hits = []
    for idx, txt, kind in L(v):
        t = norm(txt)
        if re.search(r'ЕРАЛАШ\s*№\s*' + str(num) + r'(?!\d)', t) and idx < len(L(v)) * 0.85:
            hits.append(idx)
    head = None; verb = None
    for idx in hits:
        joined = L(v)[idx][1] + ' ' + (L(v)[idx+1][1] if idx+1 < len(L(v)) else '')
        if re.search(r'Детский\s+юмористический(?:\s+\S+){0,4}\s+киножурнал', re.sub(r'\s+', ' ', joined)):
            head = idx; verb = joined[:160]; break
    if head is None and num == 49:
        # номер съеден OCR (вето-1 g1): голова v14 @1993 «ЕРАЛАШ № ^’ Детский юмористический киножурнал»
        idx = 1993; joined = L(v)[idx][1]
        if 'ЕРАЛАШ №' in joined and 'Детский юмористический киножурнал' in joined:
            head = idx; verb = joined[:160]
    if head is None:
        report.append((i, r['title'], v, 'ГОЛОВА НЕ НАЙДЕНА', hits)); continue
    if r['genre'] == CANON_E:
        report.append((i, r['title'], v, f'уже канон @{head}', None)); continue
    SET[str(i)] = {'field': 'genre', 'before': r['genre'], 'after': CANON_E, 'vol': v, 'line': head,
                   'class': 'canon', 'note': f'печатная голова: «{verb.strip()}»'}
# ── Фитиль v10 ──
CANON_F = 'Всесоюзный сатирический киножурнал'
for i, r in enumerate(cat):
    if i in S or r['source'] != 'v10_1976-1977': continue
    m = re.match(r'^Фитиль № (\d+)$', r['title'])
    if not m or r['genre'] == CANON_F: continue
    num = int(m.group(1))
    head = None; verb = None
    for idx, txt, kind in L('v10'):
        t = norm(txt)
        if re.search(r'ФИТИЛЬ\s*№\s*' + str(num) + r'(?!\d)', t) and idx < 3400:
            joined = ' '.join(L('v10')[j][1] for j in range(idx, idx+3))
            if 'Киножурнал' in joined:
                head = idx; verb = re.sub(r'\s+', ' ', joined)[:200]; break
    if head is None:
        report.append((i, r['title'], 'v10', 'ГОЛОВА НЕ НАЙДЕНА', None)); continue
    SET[str(i)] = {'field': 'genre', 'before': r['genre'], 'after': CANON_F, 'vol': 'v10', 'line': head,
                   'class': 'canon', 'note': f'печатно «Киножурнал» (сокращение тома v10); канон серии; голова: «{verb.strip()}»'}
res = {'set': SET, 'confirm': {}, 'dict': {'canon': [CANON_E, CANON_F]}}
json.dump(res, open('scripts/k1_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('SET', len(SET))
from collections import Counter
print(Counter((v['before'], v['after']) for v in SET.values()))
for x in report: print('REPORT', x)
