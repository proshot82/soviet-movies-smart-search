# -*- coding: utf-8 -*-
import json, re, sys
def norm(s):
    s = s.upper()
    t = str.maketrans({'0':'О','°':'О','4':'Ч','3':'З','I':'1','Й':'И','Ё':'Е','A':'А','B':'В','C':'С','E':'Е','H':'Н','K':'К','M':'М','O':'О','P':'Р','T':'Т','X':'Х','Y':'У'})
    s = s.translate(t).replace('П','Н')
    return re.sub(r'[^А-ЯЁЗ1-9]', '', s)
cat = json.load(open('state/catalog_f5_s4.json', encoding='utf-8'))
ids = [int(x) for x in sys.argv[1:]]
vols = {}
for c in ids:
    r = cat[c]
    v = r['source'].split('_')[0]
    if v not in vols: vols[v] = json.load(open(f'work/{v}_lines.json', encoding='utf-8'))
    L = vols[v]
    stem = re.split(r'[(«]', r['title'])[0].strip()
    needle = norm(stem)[:16]
    print(f'=== cat{c} {v} y={r["year"]} {r["title"][:40]!r} | studio={r["studio"]!r}')
    hits = [e for e in L if needle and needle in norm(e[1])]
    shown = 0
    for e in hits:
        if shown >= 3: break
        i = e[0]
        for x in L:
            if i-4 <= x[0] <= i+2: print('   ', x[0], '|', x[1][:145])
        print('    ---')
        shown += 1
    if not hits: print('    НЕ НАЙДЕНО:', needle)
