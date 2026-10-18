# -*- coding: utf-8 -*-
"""П4 a1 — локализация точечных целей."""
import json, re, sys
sys.path.insert(0, 'scripts')
from g_locate_cowork import norm

TARGETS = [
 (388,  'v1', 'ПИЛСУДСКИЙ КУПИЛ ПЕТЛЮРУ'),
 (464,  'v1', 'ЗЕМЛЯ В ПЛЕНУ'),
 (470,  'v1', 'ТУРБАЕВСКАЯ'),
 (2024, 'v2', 'КОНЦЕРТ МАСТЕРОВ УКРАИНСКОГО'),
 (2525, 'v3', 'ВЕСЕЛЫЙ ЗАГОВОР'),
 (2739, 'v3', '01-99'),
 (3318, 'v3', 'НИКУДА БОЛЬШЕ НЕ НАДО'),
 (5244, 'v10', 'ДОЛГИ НАШИ'),
 (5890, 'v12', 'ВИШНЕВЫЙ ОМУТ'),
 (6966, 'v15', 'ПЕРЕХВАТ'),
 (3554, 'v4', 'ЮЖНЫЙ УЗЕЛ'),
 (1186, 'v2', 'ЗВУКОВАЯ СБОРНАЯ ПРОГРАММА'),
]
EMB = [1184, 4767, 5456, 5468, 5606, 5645, 5894, 6335, 6546, 6967, 7231]

cat = json.load(open('state/catalog_f5_y3.json', encoding='utf-8'))
out = open('work/a1_scan.txt', 'w', encoding='utf-8')
cache = {}
def lines_of(v):
    if v not in cache:
        cache[v] = json.load(open(f'work/{v}_lines.json', encoding='utf-8'))
    return cache[v]

for c, v, needle in TARGETS:
    L = lines_of(v)
    nl = [norm(t) for _, t, _ in L]
    nd = norm(needle)
    hits = [i for i, s in enumerate(nl) if nd and nd in s]
    print(f"\n########## cat{c} {v} «{cat[c]['title']}» игла={needle!r} hits={len(hits)}", file=out)
    print(f"  каталог: genre={cat[c]['genre']!r} year={cat[c]['year']!r} studio={cat[c]['studio']!r}", file=out)
    print(f"  ann_now={repr((cat[c]['annotation'] or ''))[:200]}", file=out)
    for i in hits[:8]:
        print(f"  ---- hit @{i} [{L[i][2]}]", file=out)
        for j in range(max(0,i-1), min(len(L), i+14)):
            t = L[j][1].strip()
            if t:
                print(f"    {j}: {t[:250]}", file=out)
for c in EMB:
    print(f"\n@@@@@@@@@@ EMB cat{c} {cat[c]['source']} «{cat[c]['title']}»", file=out)
    for n in range(max(0,c-1), min(len(cat), c+2)):
        r = cat[n]
        a = r['annotation'] or ''
        print(f"  --- cat{n} «{r['title']}» genre={r['genre']!r} year={r['year']!r} studio={r['studio']!r} ann_len={len(a)}", file=out)
        print(f"      ANN: {a}", file=out)
out.close()
print('done')
