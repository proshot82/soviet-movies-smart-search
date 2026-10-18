# -*- coding: utf-8 -*-
"""Ф6-П3в, второй проход: где начинается аннотация относительно строки «В ролях» статьи.
Флаг, если строка начала аннотации (ks) лежит до последней строки списка ролей (kcast) — или сразу после неё и не похожа на прозу."""
import json, re, sys
sys.path.insert(0, 'work')
import f6_p2_lib as L
src = open('work/f6_p3v_scan.py', encoding='utf-8').read()
ns = {}; exec(src[:src.index('out = {}')], ns)
cat, gap, nmap, K4, CONCERT, CAST, CR2, PROSESTART, SRC = (ns[k] for k in ('cat', 'gap', 'nmap', 'K4', 'CONCERT', 'CAST', 'CR2', 'PROSESTART', 'SRC'))
credit_strict, credit_like = ns['credit_strict'], ns['credit_like']
CREDW = re.compile(r'исполня|под управлением|под упр\.|под руководством|в исполнении|дириж[её]р|оркестр|ансамбл|хор\b|капелл|[Пп]о[её]т |[Пп]оют |[Тт]екст .{0,30}чита|[Пп]есн[яи] |[Мм]узык|[Аа]ртист|[Уу]чащиеся|[Кк]оллектив |[Тт]анц|[Хх]ореогр|[Бб]алет|[Сс]олист|[Кк]вартет|[Кк]омментатор|[Дд]иктор|[Вв]едущ|[Зз]вучат|[Ии]спользован|благодар|[Пп]омощь в съемк|[Уу]части|снимал|[Рр]ассказыва[ею]т о|[Жж]ивопись|[Аа]ккордеон|[Мм]узыкант|[Гг]онщик|[Сс]портсмен|[Аа]ттракцион|[Оо]звуч|[Дд]убл|[Кк]онсульт|[Рр]уководител')
final = set(json.load(open('work/f6_p3v_final_set.json'))) if __import__('os').path.exists('work/f6_p3v_final_set.json') else set()
res = []
for i, r in enumerate(cat):
    a = r['annotation']
    if not a or K4.search(r['title']) or K4.search(r['genre'] or '') or CONCERT.search(r['genre'] or ''): continue
    g = gap.get(i)
    if not g or 'h2' not in g: continue
    v = r['source'].split('_')[0]; Ls = L.lines(v); A, amap = nmap(a)
    h2, E = g['h2'], g['E']
    ks = None
    for k in range(h2 + 1, E):
        nk = nmap(Ls[k][1])[0]
        if len(nk) >= 6 and (A.startswith(nk[:16]) or (len(nk) < 16 and A.startswith(nk))): ks = k; break
    if ks is None:
        a16 = A[:16]
        for k in range(h2, E):
            nk = nmap(Ls[k][1])[0]
            if a16 and a16 in nk: ks = (k, nk.find(a16)); break
    if ks is None: res.append((i, r['id'], v, 'NOSTART', None, None, a[:80])); continue
    mid = isinstance(ks, tuple)
    if mid: ks, off = ks
    kcast = max([k for k in range(h2 + 1, E) if CAST.match(Ls[k][1])], default=None)
    t = Ls[ks][1]
    if kcast is not None and ks < kcast and not mid:
        res.append((i, r['id'], v, 'BEFORE-CAST', ks, kcast, t[:100]))
    elif kcast is not None and ks < kcast and mid:
        res.append((i, r['id'], v, 'BEFORE-CAST-MID', ks, kcast, a[:100]))
    elif (kcast is None or ks == kcast + 1 or ks == kcast) and not mid:
        s = t.strip()
        if not SRC.match(s) and not PROSESTART.match(s) and (CREDW.search(s[:120]) or not L.VERB.search(s)) and (credit_like(s) or CREDW.search(s[:120])):
            res.append((i, r['id'], v, 'AFTER-CAST?', ks, kcast, t[:100]))
    elif mid and kcast is not None and ks == kcast:
        res.append((i, r['id'], v, 'CAST-MID', ks, kcast, a[:100]))
json.dump(res, open('work/f6_p3v_scan2.json', 'w', encoding='utf-8'), ensure_ascii=False)
from collections import Counter
print(Counter(x[3] for x in res))
for x in res:
    if x[0] in final: continue
    print(f"cat{x[0]} id{x[1]} {x[2]} {x[3]} ks=@{x[4]} kcast=@{x[5]} | {x[6]}")
