# -*- coding: utf-8 -*-
"""Верификация-2: фрагменты из СЮЖЕТНОЙ части аннотации (55/75/92%), длина 30.
python3 work/g_verify2.py <catalog> <lines.json> <draft.json> [window]"""
import json, sys
sys.path.insert(0, 'scripts')
from g_locate_cowork import norm
cf, lf, df = sys.argv[1], sys.argv[2], sys.argv[3]
W = int(sys.argv[4]) if len(sys.argv) > 4 else 55
lines = json.load(open(lf, encoding='utf-8'))
draft = {int(k): v for k, v in json.load(open(df, encoding='utf-8')).items()}
cat = json.load(open(cf, encoding='utf-8'))
nl = [norm(t) for _, t, _ in lines]
flag = []
for c, (raw, canon, ln, src) in sorted(draft.items()):
    na = norm(cat[c]['annotation'] or '')
    win = ''.join(nl[max(0, ln-2):ln+W])
    frs = [na[int(len(na)*p):int(len(na)*p)+30] for p in (0.55, 0.75, 0.92)]
    frs = [f for f in frs if len(f) >= 15]
    hit = sum(1 for fr in frs if fr in win)
    if hit == 0:
        flag.append(c)
        print(f"cat{c} ПРОВЕРИТЬ: 0/{len(frs)} сюжетных фрагм. «{cat[c]['title'][:40]}»")
print('к ручной проверке:', flag)
