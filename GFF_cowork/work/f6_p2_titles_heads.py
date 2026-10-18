# -*- coding: utf-8 -*-
"""П2-б: для не-ALT расхождений ищем печатную голову и строку указателя в томе для обоих вариантов (каталог / мастер)."""
import json, re
out = json.load(open('work/f6_p2_titles_scan.json', encoding='utf-8'))
L = {}
def norm_sp(s):
    s = (s or '').lower().replace('ё', 'е')
    s = re.sub(r'[^а-яa-z0-9]+', ' ', s).strip()
    return s
def lines(vol):
    if vol not in L:
        L[vol] = json.load(open(f'work/{vol}_lines.json', encoding='utf-8'))
    return L[vol]
def hits(vol, title, upper_only):
    nt = norm_sp(title)
    res = []
    for n, t, p in lines(vol):
        s = norm_sp(t)
        if nt and (s.startswith(nt) or (' ' + nt + ' ') in (' ' + s + ' ')):
            # голова: в исходной строке титул в верхнем регистре; указатель: строка вида «Титул — номер»
            is_head = title.upper()[:6].replace('Ё','Е') in t.upper().replace('Ё','Е')[:len(title)+15] and t[:1] != t[:1].lower()
            res.append((n, t[:110]))
    return res
for r in out:
    if r['class'] == 'ALT': continue
    vol = r['source'].split('_')[0]
    print(f"=== cat{r['cat']} ({vol}) [{r['class']}] title={r['title']!r} | canon={r['title_canon']!r} | xlsx={r['xlsx_title']!r} | num {r['num']}")
    base = re.sub(r'\s*\(«.*$', '', r['title']).strip()
    for lab, q in (('T', base), ('C', r['title_canon'])):
        if lab == 'C' and norm_sp(q) == norm_sp(base): continue
        h = hits(vol, q, False)
        print(f"  [{lab}] {q!r}: {len(h)} hits")
        for n, t in h[:5]:
            print(f"     @{n} {t}")
