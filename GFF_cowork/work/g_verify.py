# -*- coding: utf-8 -*-
"""Верификация локализаций: фрагменты каталожной аннотации должны находиться
в окне тома после головы. Запуск: python3 work/g_verify.py <vol_label> <lines.json> <draft.json> [window]"""
import json, sys
sys.path.insert(0, 'scripts')
from g_locate_cowork import norm

vol, lf, df = sys.argv[1], sys.argv[2], sys.argv[3]
W = int(sys.argv[4]) if len(sys.argv) > 4 else 55
lines = json.load(open(lf, encoding='utf-8'))
draft = {int(k): v for k, v in json.load(open(df, encoding='utf-8')).items()}
import os
cat = json.load(open(os.environ.get('F5_CAT', 'state/catalog_f5_g12.json'), encoding='utf-8'))
nl = [norm(t) for _, t, _ in lines]
fails = 0
for c, (raw, canon, ln, src) in sorted(draft.items()):
    r = cat[c]
    ann = r['annotation'] or ''
    win = ''.join(nl[max(0, ln-2):ln+W])
    na = norm(ann)
    if not na:
        print(f"cat{c}: АННОТАЦИИ НЕТ в каталоге — проверить руками")
        continue
    # три фрагмента по 28 симв.: начало, середина, конец
    frs = []
    for pos in (0, max(0, len(na)//2 - 14), max(0, len(na)-28)):
        fr = na[pos:pos+28]
        if len(fr) >= 15:
            frs.append(fr)
    hit = sum(1 for fr in frs if fr in win)
    year_ok = str(r['year']) in ''.join(lines[i][1] for i in range(max(0,ln-2), min(len(lines), ln+6))) if r['year'] else None
    status = 'OK' if hit >= 1 else 'FAIL'
    if hit == 0: fails += 1
    print(f"cat{c} {status}: фрагм {hit}/{len(frs)}, год в голове: {year_ok}, «{r['title'][:35]}»")
print('FAILS:', fails)
