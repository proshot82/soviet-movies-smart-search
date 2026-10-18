# -*- coding: utf-8 -*-
"""Ф6-П3в: титры внутри аннотаций киножурналов/альманахов/киносборников (k4) — покрытые аннотацией печатные строки титрового вида."""
import json, re, sys
sys.path.insert(0, 'work')
import f6_p2_lib as L
src = open('work/f6_p3v_scan.py', encoding='utf-8').read()
ns = {}; exec(src[:src.index('out = {}')], ns)
cat, gap, nmap, K4, CONCERT = ns['cat'], ns['gap'], ns['nmap'], ns['K4'], ns['CONCERT']
credit_strict, probes = ns['credit_strict'], ns['probes']
out = {}
for i, r in enumerate(cat):
    a = r['annotation']
    if not a or not (K4.search(r['title']) or K4.search(r['genre'] or '')): continue
    g = gap.get(i)
    if not g or 'h2' not in g: continue
    v = r['source'].split('_')[0]; Ls = L.lines(v); A, amap = nmap(a)
    hits = []
    for k in range(g['h2'] + 1, g['E']):
        t = Ls[k][1]
        if not t.strip(): continue
        tn = nmap(t)[0]; pr = probes(tn)
        if not pr: continue
        hit = sum(1 for p in pr if p in A)
        if hit * 2 < len(pr): continue
        if credit_strict(t): hits.append((k, t[:150]))
    if hits: out[i] = {'id': r['id'], 'title': r['title'], 'genre': r['genre'], 'vol': v, 'concert': bool(CONCERT.search(r['genre'] or '')), 'hits': hits, 'ann': a[:150]}
json.dump(out, open('work/f6_p3v_scan_k4.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('k4-записей с титрами в аннотации:', len(out), 'строк:', sum(len(x['hits']) for x in out.values()))
for i, x in sorted(out.items()):
    print(f"cat{i} id{x['id']} {x['vol']} «{x['title'][:36]}» ({x['genre'][:28]}){' [концерт]' if x['concert'] else ''} | ANN: {x['ann'][:60]}")
    for k, t in x['hits']: print(f"    @{k}: {t[:120]}")
