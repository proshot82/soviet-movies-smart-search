# -*- coding: utf-8 -*-
"""s2: локализация голов для studio_empty (нормализованный поиск титула)."""
import json, re
def norm(s):
    s = s.upper()
    table = str.maketrans({'0':'О','°':'О','4':'Ч','3':'З','I':'1','Й':'И','Ё':'Е',
        'A':'А','B':'В','C':'С','E':'Е','H':'Н','K':'К','M':'М','O':'О','P':'Р',
        'T':'Т','X':'Х','Y':'У'})
    s = s.translate(table)
    s = s.replace('П','Н')  # П↔Н гомоглиф по конвенции g5+ (одностороннее схлопывание)
    return re.sub(r'[^А-ЯЁЗ1-9]', '', s)
cat = json.load(open('state/catalog_f5_s1.json', encoding='utf-8'))
targets = [(854,'v1'),(861,'v1'),(1072,'v1'),(2106,'v2'),(3064,'v3'),(3284,'v3'),
           (4738,'v8'),(4797,'v8'),(4850,'v8'),(5244,'v10'),(5693,'v11'),(5718,'v11'),
           (6966,'v15'),(7166,'v15')]
vols = {}
for c, v in targets:
    if v not in vols:
        vols[v] = json.load(open(f'work/{v}_lines.json', encoding='utf-8'))
    L = vols[v]
    title = cat[c]['title']
    stem = re.split(r'[(«]', title)[0].strip()
    needle = norm(stem)[:14]
    print(f'=== cat{c} {v} {title[:45]!r} → игла {needle!r}')
    hits = [e for e in L if needle and needle in norm(e[1])]
    for e in hits[:4]:
        i = e[0]
        for x in L:
            if i-1 <= x[0] <= i+2:
                print('   ', x[0], '|', x[1][:130])
        print('    ---')
    if not hits: print('    НЕ НАЙДЕНО')
